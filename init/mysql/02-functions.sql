-- 计算用户下次更新时间
CREATE FUNCTION F_next_user_update_time(
    p_is_enabled     BOOLEAN,
    p_updated_at     TIMESTAMP,
    p_activity_level TINYINT,
    p_user_level     TINYINT
)
RETURNS TIMESTAMP
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE v_interval INT;
    -- 处理新用户情况，视为当前立即更新
    IF p_updated_at IS NULL THEN
        RETURN DATE_SUB(NOW(), INTERVAL 1 SECOND);
    END IF;
    -- 不可用用户直接跳过
    IF p_is_enabled IS FALSE THEN
        RETURN DATE_ADD(NOW(), INTERVAL 99999999 SECOND);
    END IF;
    -- 查询策略
    SELECT interval_seconds
    INTO v_interval
    FROM D_activity_strategy
    WHERE activity_level = p_activity_level
      AND user_level = p_user_level
    LIMIT 1;
    -- 默认1天
    SET v_interval = IFNULL(v_interval, 86400);
    -- 查询策略
    RETURN DATE_ADD(p_updated_at, INTERVAL v_interval SECOND);
END;

-- 计算用户下次更新时间
CREATE FUNCTION F_next_clan_update_time(
    p_is_enabled     BOOLEAN,
    p_updated_at     TIMESTAMP
)
RETURNS TIMESTAMP
DETERMINISTIC
BEGIN
    -- 处理新用户情况，视为当前立即更新
    IF p_updated_at IS NULL THEN
        RETURN DATE_SUB(NOW(), INTERVAL 1 SECOND);
    END IF;
    -- 不可用用户直接跳过
    IF p_is_enabled IS FALSE THEN
        RETURN DATE_ADD(NOW(), INTERVAL 99999999 SECOND);
    END IF;
    -- 查询策略，默认6小时
    RETURN DATE_ADD(p_updated_at, INTERVAL 21600 SECOND);
END;

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
        WHEN diff <= 86400 THEN 1
        WHEN diff <= 259200 THEN 2
        WHEN diff <= 604800 THEN 3
        WHEN diff <= 2592000 THEN 4
        WHEN diff <= 7776000 THEN 5
        WHEN diff <= 15552000 THEN 6
        WHEN diff <= 31536000 THEN 7
        ELSE 8
    END;
END;