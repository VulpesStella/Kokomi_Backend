INSERT INTO D_user_activity_strategy 
    (user_level,activity_level,interval_seconds,description)
VALUES
    -- 普通用户
    (0, 0, 90 * 86400, '90d'),
    (0, 1, 86400 + 7200, '26h'),
    (0, 2, 2 * 86400, '2d'),
    (0, 3, 3 * 86400, '3d'),
    (0, 4, 5 * 86400, '5d'),
    (0, 5, 7 * 86400, '7d'),
    (0, 6, 15 * 86400, '15d'),
    (0, 7, 20 * 86400, '20d'),
    (0, 8, 30 * 86400, '30d'),
    (0, 9, 90 * 86400, '90d'),
    -- recent用户
    (1, 0, 30 * 86400, '30d'),
    (1, 1, 1 * 3600, '1h'),
    (1, 2, 2 * 3600, '2h'),
    (1, 3, 3 * 3600, '3h'),
    (1, 4, 4 * 3600, '4h'),
    (1, 5, 6 * 3600, '6h'),
    (1, 6, 8 * 3600, '8h'),
    (1, 7, 12 * 3600, '12h'),
    (1, 8, 30 * 86400, '30d'),
    (1, 9, 60 * 86400, '60d'),
    -- recents用户
    (2, 0, 30 * 86400, '30d'),
    (2, 1, 10 * 60, '10m'),
    (2, 2, 20 * 60, '20m'),
    (2, 3, 25 * 60, '25m'),
    (2, 4, 30 * 60, '30m'),
    (2, 5, 60 * 60, '60m'),
    (2, 6, 15 * 86400, '15d'),
    (2, 7, 20 * 86400, '20d'),
    (2, 8, 30 * 86400, '30d'),
    (2, 9, 60 * 86400, '60d');

INSERT INTO D_clan_activity_strategy 
    (clan_level,activity_level,interval_seconds,description)
VALUES
    -- 普通用户
    (0, 0, 30 * 86400, '30d'),
    (0, 1, 6 * 3600,   '6h'),
    (0, 2, 12 * 3600,  '12h'),
    (0, 3, 26 * 3600,  '26h');

INSERT INTO D_ranking_battles_limit 
    (tier, battles_limit) 
VALUES
    (6, 40),
    (7, 40),
    (8, 40),
    (9, 50),
    (10, 60),
    (11, 60);

INSERT INTO D_ship_type 
    (id, name) 
VALUES
    (1, 'AirCarrier'),
    (2, 'Battleship'),
    (3, 'Cruiser'),
    (4, 'Destroyer'),
    (5, 'Submarine');

INSERT INTO D_ship_nation 
    (id, name) 
VALUES
    (1, 'usa'),
    (2, 'japan'),
    (3, 'germany'),
    (4, 'uk'),
    (5, 'ussr'),
    (6, 'france'),
    (7, 'italy'),
    (8, 'pan_asia'),
    (9, 'europe'),
    (10, 'netherlands'),
    (11, 'commonwealth'),
    (12, 'pan_america'),
    (13, 'spain');

INSERT INTO D_ship_rarity 
    (id, name) 
VALUES
    (1, 'Common'),
    (2, 'Uncommon'),
    (3, 'Rare'),
    (4, 'Epic'),
    (5, 'Legendary');

INSERT INTO D_metric_name
    (name)
VALUES
    ('battles'),
    ('wins'),
    ('damage'),
    ('frags'),
    ('exp'),
    ('survived'),
    ('scouting_dmg'),
    ('potential_dmg'),
    ('planes'),
    ('rating');

INSERT INTO T_base_id
    (meta)
VALUES
    ('user'),
    ('clan'),
    ('ship');

INSERT INTO T_metric_level_thresholds 
    (metric_id, threshold)
VALUES
    (3, 0.8), (3, 0.95), (3, 1.0), (3, 1.1), (3, 1.2), (3, 1.4), (3, 1.7),
    (4, 0.2), (4, 0.3), (4, 0.6), (4, 1.0), (4, 1.3), (4, 1.5), (4, 2.0);

INSERT INTO T_tracking_meta 
    (tracking_key, tracking_type) 
VALUES
    ('base_table', 'archive_time'),
    ('ship_stats', 'update_time'),
    ('clan_season', 'refresh_time');

INSERT INTO T_database_meta 
    (metric_key) 
VALUES
    ('mysql_tables'),
    ('mysql_rows'),
    ('mysql_size_kb'),
    ('sqlite_files'),
    ('sqlite_size_kb');

INSERT INTO T_table_meta 
    (metric_key, table_name) 
VALUES
    ('base_users', 'user_base'),
    ('base_clans', 'clan_base'),
    ('base_ships', 'ship_base'),
    ('planned_users', 'user_stats'),
    ('planned_clans', 'clan_users'),
    ('total_users', 'user_pvp'),
    ('ship_entries', 'user_pvp'),
    ('total_battles', 'user_pvp'),
    ('leaderboard_rows', 'ship_pvp_leaderboard');

INSERT INTO T_refresh_stats 
    (status)
VALUES
    ('overdue'),
    ('within_24h'),
    ('within_week'),
    ('within_month'),
    ('within_quarter');

INSERT INTO T_refresh_hourly_stats
    (planned_hour)
VALUES
    (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),
    (11),(12),(13),(14),(15),(16),(17),(18),(19),(20),
    (21),(22),(23),(24);