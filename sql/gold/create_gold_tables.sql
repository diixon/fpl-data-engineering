-- teams: minimal dimension table (id + names only). None of our 6 dashboard 
-- questions ask about teams directly - this table exists mainly to help 
-- disambiguate players who share the same web_name, by showing their team.
create table teams(
team_id int primary key,
name text not null,
short_name text not null
);

-- players: denormalized (position and team_name stored directly, not IDs) 
-- since this is a small, overwrite-pattern table (~600 rows). This keeps 
-- dashboard queries simple and fast - no join needed at query time. 
-- Risk: if the ETL join logic has a bug, a wrong name could land here 
-- undetected. Mitigated through testing/validation of the transformation 
-- script, not by assuming the logic is bug-proof.
create table players(
player_id int primary key,
web_name text not null,
position text not null,
team_name text not null,
current_price numeric(3,1) not null,
injury_status text not null check(injury_status in ('available', 'injured', 'doubtful', 'suspended', 'unavailable'))
);

-- player_gameweek_performance: kept NORMALIZED (player_id only, no web_name) 
-- - unlike players, this is an append-only fact table growing every gameweek 
-- (~600 players x 38 gameweeks = 22,000+ rows/season). Denormalizing here 
-- would multiply storage cost and make any name correction expensive across 
-- thousands of rows, unlike the ~600-row players table where that cost is trivial.
create table player_gameweek_performance(
player_id int,
gameweek int,
minutes int not null,
goals_scored int not null,
assists int not null,
clean_sheets int not null,
total_points int not null,
bonus int not null,
bps int not null,
expected_goals numeric(4,2) not null,
expected_assists numeric(4,2) not null,
constraint pgp_p_id foreign key (player_id) references players(player_id),
constraint pgp_pk primary key (player_id, gameweek)
);

-- player_price_history: grain = one row per PRICE CHANGE EVENT, not per 
-- gameweek - same information as a weekly snapshot, but fewer rows and 
-- storage, with a gameweek column marking exactly when the change happened.
-- 
-- Unlike players/teams (overwrite pattern, self-correcting on next run), 
-- this table is APPEND-ONLY - bad data here has no automatic safety net. 
-- So load_date/source_run_id are kept here (unlike most Gold tables) for 
-- traceability, to speed up debugging if a bad price value is ever found.
create table player_price_history(
player_id int,
gameweek int,
new_price numeric(3,1) not null,
price_change_amount numeric(2,1) not null,
load_date timestamp not null,
source_run_id bigint not null,
constraint pph_kp primary key(player_id, gameweek),
constraint fk_pph_pr_id foreign key (source_run_id) references pipeline_runs(run_id),
constraint fk_pph_p_id foreign key (player_id) references players (player_id)
);

-- fixture_results: denormalized (team names direct, not team_id) - small 
-- table (~380 rows/season), same reasoning as players: cheap to denormalize, 
-- speeds up dashboard queries.
--
-- APPEND-ONLY like player_price_history (a finished match result is 
-- permanent, never overwritten) - so load_date/source_run_id are kept here 
-- too, for traceability if a bad result ever needs tracing back to its source.
create table fixture_results(
fixture_id int primary key,
gameweek int not null,
kickoff_time timestamp not null,
team_h_name text not null,
team_a_name text not null,
team_h_score int not null,
team_a_score int not null,
team_h_difficulty int not null,
team_a_difficulty int not null,
load_date timestamp not null,
source_run_id bigint not null,
constraint fk_fr_pr_id foreign key (source_run_id) references pipeline_runs (run_id)
);