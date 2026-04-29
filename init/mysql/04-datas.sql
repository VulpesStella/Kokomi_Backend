INSERT INTO D_activity_strategy 
    (user_level,activity_level,interval_seconds,description)
VALUES
    -- 普通用户
    (0, 0, 30 * 86400, '30d'),
    (0, 1, 1 * 86400, '1d'),
    (0, 2, 2 * 86400, '2d'),
    (0, 3, 3 * 86400, '3d'),
    (0, 4, 5 * 86400, '5d'),
    (0, 5, 7 * 86400, '7d'),
    (0, 6, 15 * 86400, '15d'),
    (0, 7, 20 * 86400, '20d'),
    (0, 8, 30 * 86400, '30d'),
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
    -- recents用户
    (2, 0, 30 * 86400, '30d'),
    (2, 1, 10 * 60, '10m'),
    (2, 2, 20 * 60, '20m'),
    (2, 3, 25 * 60, '25m'),
    (2, 4, 30 * 60, '30m'),
    (2, 5, 60 * 60, '60m'),
    (2, 6, 15 * 86400, '15d'),
    (2, 7, 20 * 86400, '20d'),
    (2, 8, 30 * 86400, '30d');

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
    ('damage'),
    ('frags'),
    ('exp'),
    ('win_rate'),
    ('survived_rate'),
    ('scouting_dmg'),
    ('potential_dmg');

INSERT INTO T_metric_level_thresholds 
    (metric_id, threshold)
VALUES
    (1, 0.8), (1, 0.95), (1, 1.0), (1, 1.1), (1, 1.2), (1, 1.4), (1, 1.7),
    (2, 0.2), (2, 0.3), (2, 0.6), (2, 1.0), (2, 1.3), (2, 1.5), (2, 2.0);

INSERT INTO T_tracking_meta 
    (tracking_key, tracking_type) 
VALUES
    ('ship_users', 'archive_time'),
    ('ship_battles', 'archive_time');