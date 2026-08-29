create table bronze_players(
bronze_id bigint generated always as identity primary key,
player_id int not null,
-- raw_json: stored as JSONB instead of flat columns, because the source has 
-- many nested fields (e.g. price_change_projections). Flattening now would be 
-- messy and fragile if the API changes. Parsing happens later, in Silver.
raw_json jsonb not null,
load_date timestamp not null,
-- snapshot_type: marks *when* this row was pulled (e.g. before deadline, 
-- after gameweek). Lets us compare a player's data pre-match vs post-match, 
-- and test whether our pick was justified based on the info available at the time.
snapshot_type text not null,
run_id bigint not null,
constraint fk_bp_pr_runid foreign key (run_id) references pipeline_runs(run_id)
);

create table bronze_fixtures(
bronze_id bigint generated always as identity primary key,
fixture_id int not null,
raw_json jsonb not null,
load_date timestamp not null,
-- snapshot_type: 'finished' in the JSON is only true/false, so it can't tell 
-- us if a pull happened before kickoff, mid-match, or after the final whistle. 
-- This column captures that timing explicitly, since 'finished' alone isn't enough.
snapshot_type text not null,
run_id bigint not null,
constraint fk_bf_pr_runid foreign key (run_id) references pipeline_runs(run_id)
);

create table bronze_teams(
bronze_id bigint generated always as identity primary key,
team_id int not null,
raw_json jsonb not null,
load_date timestamp not null,
-- snapshot_type: fields like points, position, and played stay fixed within 
-- a gameweek, but change once matches finish. This column marks whether the 
-- pull happened before or after that update.
snapshot_type text not null,
run_id bigint not null,
constraint fk_bt_pr_runid foreign key (run_id) references pipeline_runs(run_id)
);

create table bronze_event(
bronze_id bigint generated always as identity primary key,
player_id int not null,
-- gameweek: the raw JSON has no field showing which gameweek this data is 
-- for; it's only known from the URL we called (event/{gw}/live/). We must 
-- store it manually, or this data becomes meaningless once mixed with other weeks.
gameweek int not null,
raw_json jsonb not null,
load_date timestamp not null,
-- snapshot_type: this endpoint is literally "live" - data changes minute to 
-- minute during a match. This column marks exactly when we pulled it 
-- (e.g. mid-match vs after final whistle), since the numbers won't match otherwise.
snapshot_type text not null,
run_id bigint not null,
constraint fk_be_pr_runid foreign key (run_id) references pipeline_runs(run_id),
constraint uq_playerid_gameweek unique (player_id, gameweek)
);

-- bronze_element_types: lookup data for player positions (GK/DEF/MID/FWD).
-- Unlike other Bronze tables, this is flattened into real columns instead of 
-- JSONB, since every field is flat with no nested arrays - flattening here 
-- still counts as "raw, unmodified storage," just structured differently.
-- No snapshot_type: this data is stable all season, doesn't change mid-gameweek.
create table bronze_element_types(
bronze_id bigint generated always as identity primary key,
element_type_id int not null,
plural_name text not null,
singular_name text not null,
singular_name_short text not null,
squad_select int not null,
squad_min_play int not null,
squad_max_play int not null,
element_count int not null,
load_date timestamp not null,
run_id bigint not null,
constraint fk_bet_pr_runid foreign key (run_id) references pipeline_runs(run_id)
);