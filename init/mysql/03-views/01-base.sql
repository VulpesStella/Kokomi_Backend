CREATE VIEW V_user_activity_distribution AS
SELECT
    lvl.activity_level,
    COUNT(s.activity_level) AS cnt
FROM (
    SELECT 0 AS activity_level UNION ALL
    SELECT 1 UNION ALL
    SELECT 2 UNION ALL
    SELECT 3 UNION ALL
    SELECT 4 UNION ALL
    SELECT 5 UNION ALL
    SELECT 6 UNION ALL
    SELECT 7 UNION ALL
    SELECT 8 UNION ALL
    SELECT 9
) lvl
LEFT JOIN T_user_stats s
    ON lvl.activity_level = s.activity_level
GROUP BY lvl.activity_level
ORDER BY lvl.activity_level;

CREATE VIEW V_clan_league_distribution AS
SELECT
    l.league,
    COUNT(c.league) AS cnt
FROM (
    SELECT 1 AS league UNION ALL
    SELECT 2 UNION ALL
    SELECT 3 UNION ALL
    SELECT 4 UNION ALL
    SELECT 5
) l
LEFT JOIN T_clan_base c
    ON l.league = c.league
GROUP BY l.league
ORDER BY l.league;

CREATE VIEW V_user_basic_with_clan AS
SELECT
    u.account_id,
    u.username,
    u.register_time,
    u.insignias,
    uc.clan_id,
    c.tag AS clan_tag,
    c.league,
    c.updated_at
FROM T_user_base u
LEFT JOIN T_user_clan uc
    ON u.account_id = uc.account_id
LEFT JOIN T_clan_base c
    ON uc.clan_id = c.clan_id;

CREATE VIEW V_ship_ranking_stats AS
SELECT 
    b.ship_id, 
    l.battles_limit AS min_battles,
    s.battles AS stats_battles,
    s.win_rate, 
    s.avg_damage, 
    s.avg_frags
FROM T_ship_base b
INNER JOIN T_ship_stats_by_battles s ON b.ship_id = s.ship_id
INNER JOIN D_ranking_battles_limit l ON b.tier = l.tier
WHERE b.is_enabled = 1 
    AND b.is_old = 0
    AND b.tier > 5; 

CREATE VIEW V_version_battles_total AS
SELECT 
    game_version,
    SUM(battles) AS total_battles
FROM ARCH_ship_stats_by_recent
GROUP BY game_version;