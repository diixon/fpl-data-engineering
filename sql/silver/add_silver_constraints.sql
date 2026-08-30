-- Foreign keys are added here, separately from create_silver_tables.sql, 
-- because tables were built first (Bronze -> Silver, in dependency order), 
-- then constraints were wired up once every referenced table existed. 
-- Even though Silver tables mainly exist to feed Gold, these FKs still matter: 
-- they catch bad/broken references (e.g. an invalid team_id) the moment they 
-- try to enter Silver, rather than letting them surface later in Gold.

alter table silver_players
add constraint fk_sp_set_id
foreign key (element_type_id) references silver_element_types (element_type_id);

alter table silver_players
add constraint fk_sp_st_id
foreign key (team_id) references silver_teams (team_id);

alter table silver_players
add constraint fk_sp_pr_id
foreign key (source_run_id) references pipeline_runs (run_id);

alter table silver_teams
add constraint fk_st_pr_id
foreign key (source_run_id) references pipeline_runs (run_id);

alter table silver_fixtures
add constraint fk_sf_st_hid
foreign key (team_h) references silver_teams (team_id);

alter table silver_fixtures
add constraint fk_sf_st_aid
foreign key (team_a) references silver_teams (team_id);

alter table silver_fixtures
add constraint fk_sf_pr_id
foreign key (source_run_id) references pipeline_runs (run_id);

alter table silver_element_types
add constraint fk_set_pr_id
foreign key (source_run_id) references pipeline_runs (run_id);

alter table silver_player_gameweek_stats
add constraint fk_spgs_sp_id
foreign key (player_id) references silver_players (player_id);

alter table silver_player_gameweek_stats
add constraint fk_spgs_pr_id
foreign key (source_run_id) references pipeline_runs (run_id);