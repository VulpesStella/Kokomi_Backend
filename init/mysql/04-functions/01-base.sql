-- DELIMITER //

CREATE FUNCTION F_user_next_refresh_at(
    p_user_level     TINYINT,
    p_activity_level TINYINT
) RETURNS TIMESTAMP
    READS SQL DATA
    NOT DETERMINISTIC
BEGIN
    DECLARE v_interval INT;

    -- 查询用户对应的刷新间隔，未找到则默认 30 H (108000 秒)
    SELECT interval_seconds
    INTO v_interval
    FROM D_user_activity_strategy
    WHERE activity_level = p_activity_level
      AND user_level = p_user_level
    LIMIT 1;

    SET v_interval = IFNULL(v_interval, 108000);

    -- 返回绝对时间戳：当前时间 + 间隔
    RETURN NOW() + INTERVAL v_interval SECOND;
END;


CREATE FUNCTION F_clan_next_refresh_at(
    p_activity_level TINYINT
) RETURNS TIMESTAMP
    READS SQL DATA
    NOT DETERMINISTIC
BEGIN
    DECLARE v_interval INT;

    -- 查询公会对应的刷新间隔，未找到则默认 30 H (108000 秒)
    SELECT interval_seconds
    INTO v_interval
    FROM D_clan_activity_strategy
    WHERE activity_level = p_activity_level
      AND clan_level = 0
    LIMIT 1;

    SET v_interval = IFNULL(v_interval, 108000);

    -- 返回绝对时间戳：当前时间 + 间隔
    RETURN NOW() + INTERVAL v_interval SECOND;
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