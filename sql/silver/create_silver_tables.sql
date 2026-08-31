-- silver_players: cleaned, current-snapshot player info (overwrite pattern - 
-- one row per player, no history). References to team/position are kept as 
-- raw IDs; translation to readable text happens later, in Gold.
create table silver_players(
player_id int primary key,
web_name text not null,
element_type_id int not null,
team_id int not null,
current_price numeric(3,1) not null,       -- converted from now_cost (e.g. 60 -> 6.0)
injury_status text not null check(injury_status in ('available', 'injured', 'doubtful', 'suspended', 'unavailable')),
load_date timestamp not null,
source_run_id bigint not null              -- traces back to pipeline_runs.run_id (FK added later)
);

-- silver_teams: cleaned, current-snapshot team info (overwrite pattern - no 
-- history needed, since none of our dashboard questions require team standings 
-- history, only current state).
create table silver_teams(
team_id int primary key,
name text not null,
short_name text not null,
points int not null,
played int not null,
position int not null,
win int not null,
draw int not null,
loss int not null,
load_date timestamp not null,
source_run_id bigint not null
);

-- silver_fixtures: only finished matches are loaded here (finished = true), 
-- so score columns are safely NOT NULL. Unplayed/future fixtures are not 
-- pulled into Silver yet. Difficulty ratings kept since managers use them 
-- heavily for transfer decisions.
create table silver_fixtures(
fixture_id int primary key,
gameweek int not null,
kickoff_time timestamp not null,
team_h int not null,
team_a int not null,
team_h_score int not null,
team_a_score int not null,
team_h_difficulty int not null,
team_a_difficulty int not null,
load_date timestamp not null,
source_run_id bigint not null
);

-- silver_element_types: cleaned lookup for player positions (GK/DEF/MID/FWD). 
-- Stable, rarely-changing data - overwrite pattern, no snapshot_type needed.
create table silver_element_types(
element_type_id int primary key,
plural_name text not null,
singular_name text not null,
singular_name_short text not null,
squad_select int not null,
squad_min_play int not null,
squad_max_play int not null,
element_count int not null,
load_date timestamp not null,
source_run_id bigint not null
);

-- silver_player_gameweek_stats: one row per player per gameweek, appended 
-- (not overwritten) - each gameweek's stats are a permanent, distinct fact, 
-- unlike current_price/injury_status which get replaced. Only summary stats 
-- kept; the deeply nested 'explain' breakdown from bronze_event is dropped, 
-- since no dashboard question needs point-by-point justification.
create table silver_player_gameweek_stats(
player_id int,
gameweek int,
transfers_in_event int not null,
minutes int not null,
goals_scored int not null,
assists int not null,
clean_sheets int not null,
total_points int not null,
bonus int not null,
bps int not null,
expected_goals numeric(3,2) not null,
expected_assists numeric(3,2) not null,
load_date timestamp not null,
source_run_id bigint not null,
constraint pk_pid_gw primary key (player_id, gameweek)
);