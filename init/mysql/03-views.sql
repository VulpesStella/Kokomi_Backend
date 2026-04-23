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
    SELECT 8
) lvl
LEFT JOIN T_user_stats s
    ON lvl.activity_level = s.activity_level
GROUP BY lvl.activity_level
ORDER BY lvl.activity_level;

CREATE VIEW V_user_basic_with_clan AS
SELECT
    u.account_id,
    u.username,
    uc.clan_id,
    c.tag AS clan_tag,
    c.league,
    uc.updated_at
FROM T_user_base u
LEFT JOIN T_user_clan uc
    ON u.account_id = uc.account_id
LEFT JOIN T_clan_base c
    ON uc.clan_id = c.clan_id;

CREATE VIEW V_user_update_schedule AS
SELECT
    t.*,
    (t.next_update_time <= NOW()) AS is_due
FROM (
    SELECT
        u.account_id,
        F_next_user_update_time(
            u.is_enabled,
            u.updated_at,
            u.activity_level,
            IFNULL(c.user_level, 0)
        ) AS next_update_time
    FROM T_user_stats u
    LEFT JOIN T_user_config c
        ON u.account_id = c.account_id
) t;

CREATE VIEW V_clan_update_schedule AS
SELECT
    t.*,
    (t.next_update_time <= NOW()) AS is_due
FROM (
    SELECT
        c.clan_id,
        F_next_clan_update_time(
            c.is_enabled,
            c.updated_at
        ) AS next_update_time
    FROM T_clan_users c
) t;

CREATE VIEW V_user_update_stats AS
SELECT
    COUNT(*) AS total_count,
    SUM(is_due = TRUE) AS due_count,
    SUM(is_due = FALSE) AS not_due_count
FROM V_user_update_schedule;

CREATE VIEW V_clan_update_stats AS
SELECT
    COUNT(*) AS total_count,
    SUM(is_due = TRUE) AS due_count,
    SUM(is_due = FALSE) AS not_due_count
FROM V_clan_update_schedule;

CREATE VIEW V_leaderboard_summary AS
SELECT 
    ship_id,
    COUNT(*) AS total_records          -- 该船的总玩家数
FROM T_ship_pvp_leaderboard
GROUP BY ship_id;