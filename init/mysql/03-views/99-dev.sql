CREATE VIEW _V_ship_name_zh AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    r.name AS rarity,
    a.zh_cn AS zh_cn,
    a.zh_sg AS zh_sg,
    a.zh_tw AS zh_tw
FROM
    T_ship_base b
INNER JOIN T_ship_name a
    ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t
    ON b.type_id = t.id
INNER JOIN D_ship_nation n
    ON b.nation_id = n.id
INNER JOIN D_ship_rarity r
    ON b.rarity_id = r.id;

CREATE VIEW _V_ship_avg_by_battles AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS zh,
    s.battles,
    s.win_rate,
    s.avg_damage,
    s.avg_frags,
    s.avg_exp,
    s.updated_at
FROM T_ship_stats_by_battles s
INNER JOIN T_ship_base b
    ON b.ship_id = s.ship_id
INNER JOIN T_ship_name a
    ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t
    ON b.type_id = t.id
INNER JOIN D_ship_nation n
    ON b.nation_id = n.id;

CREATE VIEW _V_ship_avg_by_users AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS zh,
    s.users, 
    s.battles,
    s.rating,
    s.win_rate,
    s.avg_damage,
    s.avg_frags,
    s.avg_exp,
    s.updated_at
FROM T_ship_stats_by_users s
INNER JOIN T_ship_base b
    ON b.ship_id = s.ship_id
INNER JOIN T_ship_name a
    ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t
    ON b.type_id = t.id
INNER JOIN D_ship_nation n
    ON b.nation_id = n.id;

CREATE VIEW _V_user_max_exp_record AS
SELECT
    b.username,
    u.max_exp,
    n.zh_sg AS max_exp_ship,
    u.updated_at
FROM T_user_pvp_record u
LEFT JOIN T_user_base b
    ON u.account_id = b.account_id
LEFT JOIN T_ship_name n
    ON u.max_exp_id = n.ship_id;

CREATE VIEW _V_test_leaderboard_4277090288 AS
SELECT 
    RANK() OVER (ORDER BY rating DESC) AS `rank`,
    account_id,
    rating,
    battles,
    CONCAT(ROUND(win_rate, 2), '%') AS win_rate,
    CONCAT(ROUND(solo_rate, 2), '%') AS solo_rate,
    avg_damage,
    avg_frags,
    avg_exp,
    CONCAT(hit_ratio, '%') AS hit_ratio,
    max_exp,
    max_damage,
    -- 记录更新时间，确认数据是否最新
    updated_at
FROM T_ship_pvp_leaderboard
WHERE ship_id = 4277090288
ORDER BY rating DESC;

CREATE VIEW _V_test_leaderboard_4277090288_top50 AS
SELECT 
    RANK() OVER (ORDER BY s.rating DESC) AS `rank`,
    u.clan_tag,
    u.league,
    u.username,
    s.battles,
    s.rating,
    CASE
        WHEN s.rating < 750 THEN 1
        WHEN s.rating < 1100 THEN 2
        WHEN s.rating < 1350 THEN 3
        WHEN s.rating < 1550 THEN 4
        WHEN s.rating < 1750 THEN 5
        WHEN s.rating < 2100 THEN 6
        WHEN s.rating < 2450 THEN 7
        ELSE 8
    END AS r_l,
    CONCAT(ROUND(s.win_rate, 2), '%') AS win_rate,
    CASE
        WHEN s.win_rate < 40 THEN 1
        WHEN s.win_rate < 45 THEN 2
        WHEN s.win_rate < 50 THEN 3
        WHEN s.win_rate < 52.5 THEN 4
        WHEN s.win_rate < 55 THEN 5
        WHEN s.win_rate < 60 THEN 6
        WHEN s.win_rate < 67 THEN 7
        ELSE 8
    END AS wr_l,
    CONCAT(ROUND(s.solo_rate, 2), '%') AS solo_rate,
    CASE
        WHEN s.solo_rate < 10 THEN 1
        WHEN s.solo_rate < 30 THEN 2
        WHEN s.solo_rate < 40 THEN 3
        WHEN s.solo_rate < 50 THEN 4
        WHEN s.solo_rate < 60 THEN 5
        WHEN s.solo_rate < 70 THEN 6
        WHEN s.solo_rate < 80 THEN 7
        ELSE 8
    END AS sr_l,
    s.avg_damage,
    s.avg_damage_level AS ad_l,
    s.avg_frags,
    s.avg_frags_level AS af_l,
    s.avg_exp,
    CONCAT(s.hit_ratio, '%') AS hit_ratio,
    s.max_exp,
    s.max_damage
FROM T_ship_pvp_leaderboard s
LEFT JOIN V_user_basic_with_clan u
  ON s.account_id = u.account_id
WHERE s.ship_id = 4277090288
ORDER BY rating DESC, s.account_id ASC
LIMIT 50;

CREATE VIEW _V_test_leaderboard_clan_s33 AS
SELECT
    RANK() OVER (
        ORDER BY 
            (s.public_rating + s.stage_battles * 0.1 + s.stage_victories * 0.01) DESC,
            s.clan_id ASC
    ) AS `rank`,
    b.tag AS clan_tag,
    s.leading_team_number AS team,
    s.battles_count AS battles,
    CASE 
        WHEN s.battles_count = 0 THEN '0%'
        ELSE CONCAT(ROUND(s.wins_count / s.battles_count * 100, 2), '%')
    END AS win_rate,
    CASE
        WHEN s.battles_count = 0 THEN 0
        WHEN (s.wins_count / s.battles_count * 100) < 40 THEN 1
        WHEN (s.wins_count / s.battles_count * 100) < 45 THEN 2
        WHEN (s.wins_count / s.battles_count * 100) < 50 THEN 3
        WHEN (s.wins_count / s.battles_count * 100) < 52.5 THEN 4
        WHEN (s.wins_count / s.battles_count * 100) < 55 THEN 5
        WHEN (s.wins_count / s.battles_count * 100) < 60 THEN 6
        WHEN (s.wins_count / s.battles_count * 100) < 67 THEN 7
        ELSE 8
    END AS wr_l,
    s.league,
    s.division,
    s.public_rating AS rating,
    s.longest_winning_streak,
    s.stage_type,
    s.stage_progress,
    s.last_battle_at
FROM T_clan_stats s
LEFT JOIN T_clan_base b
  ON s.clan_id = b.clan_id
WHERE s.season = 33 AND s.battles_count > 0
ORDER BY 
    (s.public_rating + s.stage_battles * 0.1 + s.stage_victories * 0.01) DESC,
    s.clan_id ASC;

CREATE VIEW _V_test_ship_4277090288_v15_3_battles AS
SELECT
    stat_date,

    battles,
    win_rate,
    avg_damage,
    avg_frags,
    avg_exp,
    survived_rate,
    avg_scouting_damage,
    avg_potential_damage
FROM ARCH_ship_stats_by_battles
WHERE ship_id = 4277090288
  AND game_version = '15.3'
ORDER BY stat_date ASC;

CREATE VIEW _V_test_ship_4277090288_v15_3_users AS
SELECT
    stat_date,

    users,
    battles,
    win_rate,
    avg_damage,
    avg_frags,
    avg_exp,
    survived_rate,
    avg_scouting_damage,
    avg_potential_damage
FROM ARCH_ship_stats_by_users
WHERE ship_id = 4277090288
  AND game_version = '15.3'
ORDER BY stat_date ASC;

CREATE VIEW _V_test_ship_4277090288_recent AS
SELECT
    game_version,

    battles,
    wins,
    damage,
    frags,
    exp,
    survived,
    scouting_damage,
    potential_damage,

    updated_at
FROM ARCH_ship_stats_by_recent
WHERE ship_id = 4277090288
ORDER BY game_version ASC;

-- 伤害 (damage)
CREATE OR REPLACE VIEW _V_ship_record_by_damage AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS ship_name,
    r.metric_value AS damage,
    r.users_count AS damage_users,
    r.top_user_ids,
    r.updated_at
FROM T_ship_pvp_record r
INNER JOIN T_ship_base b ON r.ship_id = b.ship_id
INNER JOIN T_ship_name a ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
WHERE r.metric_id = 3;

-- 击杀 (frags)
CREATE OR REPLACE VIEW _V_ship_record_by_frags AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS ship_name,
    r.metric_value AS frags,
    r.users_count AS frags_users,
    r.top_user_ids,
    r.updated_at
FROM T_ship_pvp_record r
INNER JOIN T_ship_base b ON r.ship_id = b.ship_id
INNER JOIN T_ship_name a ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
WHERE r.metric_id = 4;

-- 经验 (exp)
CREATE OR REPLACE VIEW _V_ship_record_by_exp AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS ship_name,
    r.metric_value AS exp,
    r.users_count AS exp_users,
    r.top_user_ids,
    r.updated_at
FROM T_ship_pvp_record r
INNER JOIN T_ship_base b ON r.ship_id = b.ship_id
INNER JOIN T_ship_name a ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
WHERE r.metric_id = 5;

-- 侦查伤害 (scouting_dmg)
CREATE OR REPLACE VIEW _V_ship_record_by_scouting AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS ship_name,
    r.metric_value AS scouting_dmg,
    r.users_count AS scouting_users,
    r.top_user_ids,
    r.updated_at
FROM T_ship_pvp_record r
INNER JOIN T_ship_base b ON r.ship_id = b.ship_id
INNER JOIN T_ship_name a ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
WHERE r.metric_id = 7;

-- 潜在伤害 (potential_dmg)
CREATE OR REPLACE VIEW _V_ship_record_by_potential AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS ship_name,
    r.metric_value AS potential_dmg,
    r.users_count AS potential_users,
    r.top_user_ids,
    r.updated_at
FROM T_ship_pvp_record r
INNER JOIN T_ship_base b ON r.ship_id = b.ship_id
INNER JOIN T_ship_name a ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
WHERE r.metric_id = 8;

-- 击落飞机 (planes)
CREATE OR REPLACE VIEW _V_ship_record_by_planes AS
SELECT
    b.ship_id,
    b.tier,
    t.name AS type,
    n.name AS nation,
    a.zh_sg AS ship_name,
    r.metric_value AS planes,
    r.users_count AS planes_users,
    r.top_user_ids,
    r.updated_at
FROM T_ship_pvp_record r
INNER JOIN T_ship_base b ON r.ship_id = b.ship_id
INNER JOIN T_ship_name a ON b.ship_id = a.ship_id
INNER JOIN D_ship_type t ON b.type_id = t.id
INNER JOIN D_ship_nation n ON b.nation_id = n.id
WHERE r.metric_id = 9;