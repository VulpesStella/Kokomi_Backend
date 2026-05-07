-- DELIMITER //

-- 用户活跃度计算函数
-- 根据最后战斗时间距今的差值，返回1-9的活跃度等级
-- 活跃度越高表示用户最近越活跃（间隔时间越短）
CREATE FUNCTION F_user_activity_level(last_battle_time BIGINT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE current_ts BIGINT;
    DECLARE diff BIGINT;
    
    IF IFNULL(last_battle_time, 0) = 0 THEN
        RETURN 0;
    END IF;
    
    SET current_ts = UNIX_TIMESTAMP();
    SET diff = current_ts - last_battle_time;
    
    RETURN CASE
        WHEN diff <= 86400 THEN 1       -- 1天内
        WHEN diff <= 259200 THEN 2      -- 3天内
        WHEN diff <= 604800 THEN 3      -- 7天内
        WHEN diff <= 2592000 THEN 4     -- 30天内
        WHEN diff <= 7776000 THEN 5     -- 90天内
        WHEN diff <= 15552000 THEN 6    -- 180天内
        WHEN diff <= 31536000 THEN 7    -- 365天内
        WHEN diff <= 63072000 THEN 8    -- 730天内
        ELSE 9                           -- 超过730天
    END;
END;

-- 用户更新到期判断函数
-- 根据用户的启用状态、上次更新时间及活跃度等级，
-- 查询 D_user_activity_strategy 表获取更新间隔，判断是否需要更新
CREATE FUNCTION F_is_user_update_due(
    p_is_enabled     BOOLEAN,
    p_updated_at     TIMESTAMP,
    p_activity_level TINYINT,
    p_user_level     TINYINT
) RETURNS BOOLEAN
    READS SQL DATA
    DETERMINISTIC
BEGIN
    DECLARE v_interval INT;

    -- 新用户需要更新
    IF p_updated_at IS NULL THEN
        RETURN TRUE;
    END IF;

    -- 不可用用户不需要更新
    IF p_is_enabled IS FALSE THEN
        RETURN FALSE;
    END IF;

    -- 查询更新间隔策略
    SELECT interval_seconds
    INTO v_interval
    FROM D_user_activity_strategy
    WHERE activity_level = p_activity_level
      AND user_level = p_user_level
    LIMIT 1;

    -- 默认 1 天
    SET v_interval = IFNULL(v_interval, 86400);

    -- 判断是否到期
    RETURN p_updated_at + INTERVAL v_interval SECOND <= NOW();
END;

-- 公会更新到期判断函数
-- 根据公会的启用状态和上次更新时间，
-- 查询 D_clan_activity_strategy 表获取更新间隔，判断是否需要更新
CREATE FUNCTION F_is_clan_update_due(
    p_is_enabled     BOOLEAN,
    p_updated_at     TIMESTAMP
) RETURNS BOOLEAN
    READS SQL DATA
    DETERMINISTIC
BEGIN
    DECLARE v_interval INT;

    -- 新用户需要更新
    IF p_updated_at IS NULL THEN
        RETURN TRUE;
    END IF;

    -- 不可用用户不需要更新
    IF p_is_enabled IS FALSE THEN
        RETURN FALSE;
    END IF;

    -- 查询更新间隔策略
    SELECT interval_seconds
    INTO v_interval
    FROM D_clan_activity_strategy
    WHERE activity_level = 1
      AND clan_level = 0
    LIMIT 1;

    -- 默认 1 天
    SET v_interval = IFNULL(v_interval, 86400);

    -- 判断是否到期
    RETURN p_updated_at + INTERVAL v_interval SECOND <= NOW();
END;

-- 船只PR值计算函数
-- 根据用户的实际与预期胜率、伤害、击杀数据，
-- 通过归一化与加权公式计算综合个人评级（Personal Rating）
CREATE FUNCTION F_calculate_ship_pr(
    actual_wins DOUBLE,
    actual_dmg DOUBLE,
    actual_frags DOUBLE,
    expected_wins DOUBLE,
    expected_dmg DOUBLE,
    expected_frags DOUBLE
)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE r_wins DOUBLE;
    DECLARE r_dmg DOUBLE;
    DECLARE r_frags DOUBLE;
    DECLARE n_wins DOUBLE;
    DECLARE n_dmg DOUBLE;
    DECLARE n_frags DOUBLE;
    DECLARE pr DOUBLE;
    IF IFNULL(expected_wins, 0) = 0
        OR IFNULL(expected_dmg, 0) = 0
        OR IFNULL(expected_frags, 0) = 0 THEN
            RETURN -1.00;
    END IF;
    -- ratios
    SET r_wins = actual_wins / expected_wins;
    SET r_dmg = actual_dmg / expected_dmg;
    SET r_frags = actual_frags / expected_frags;
    -- normalization
    SET n_wins = GREATEST(0, (r_wins - 0.7) / (1 - 0.7));
    SET n_dmg = GREATEST(0, (r_dmg - 0.4) / (1 - 0.4));
    SET n_frags = GREATEST(0, (r_frags - 0.1) / (1 - 0.1));
    -- final PR
    SET pr = 700 * n_dmg + 300 * n_frags + 150 * n_wins;
    RETURN ROUND(pr, 2);
END;

-- 指标等级计算函数
-- 根据指标ID、实际值及平均值，查询 T_metric_level_thresholds 表获取阈值等级
-- 返回实际值/平均值所达到的等级（1-8），比值越高等级越高
CREATE FUNCTION F_get_metric_level(idx INT, val DOUBLE, avg DOUBLE)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE result INT;
    DECLARE r_val DOUBLE;
    IF IFNULL(avg, 0) = 0 THEN
        RETURN -1;
    END IF;
    SET r_val = val / avg;
    SELECT 1 + COUNT(*)
    INTO result
    FROM T_metric_level_thresholds
    WHERE metric_id = idx
      AND r_val >= threshold;
    RETURN result;
END;