-- 用户基础信息表
-- 存储用户的基本信息，包括用户名、注册时间等
CREATE TABLE IF NOT EXISTS T_user_base (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    username         VARCHAR(25)  NOT NULL,        -- 最大25个字符
    register_time    TIMESTAMP    DEFAULT NULL,    -- 注册时间
    insignias        VARCHAR(55)  DEFAULT NULL,    -- 徽章信息

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id)
);

-- 用户统计表
-- 存储用户的活跃度和战斗统计数据
CREATE TABLE IF NOT EXISTS T_user_stats (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    is_enabled       BOOLEAN      DEFAULT TRUE,    -- 用户是否有效
    is_public        BOOLEAN      DEFAULT TRUE,    -- 用户是否公开战绩
    activity_level   TINYINT      DEFAULT 0,       -- 用户活跃等级
    total_battles    INT          DEFAULT 0,       -- 总战斗场次
    pve_battles      INT          DEFAULT 0,       -- PvE 场次
    pvp_battles      INT          DEFAULT 0,       -- PvP 场次
    ranked_battles   INT          DEFAULT 0,       -- 排位战场次
    rating_battles   INT          DEFAULT 0,       -- 评分战场次
    karma            INT          DEFAULT 0,       -- 业力值
    last_battle_at   TIMESTAMP    DEFAULT NULL,    -- 最后战斗时间
    next_refresh_at  TIMESTAMP    DEFAULT NULL,    -- 最低下次更新时间

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id)
);

-- 用户行为记录表
-- 记录用户改名等历史行为，只追加不更新
CREATE TABLE IF NOT EXISTS T_user_action (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    username         VARCHAR(25)  NOT NULL,        -- 曾用名

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_aid (account_id),
    INDEX idx_username (username)
);

-- 用户公会关联表
-- 记录用户当前所属公会，一个用户只能属于一个公会
CREATE TABLE IF NOT EXISTS T_user_clan (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-10位的非连续数字
    clan_id          BIGINT       DEFAULT NULL,    -- 10位的非连续数字，NULL 表示无公会

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id),
    INDEX idx_cid (clan_id)
);

-- 用户 PvP 缓存表
-- 存储用户在各船只上的 PvP 原始战斗数据
CREATE TABLE IF NOT EXISTS T_user_pvp (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    battles          INT          DEFAULT 0,       -- 总战斗场次
    win_rate         FLOAT        DEFAULT 0,       -- 胜率
    avg_damage       FLOAT        DEFAULT 0,       -- 场均伤害
    avg_frags        FLOAT        DEFAULT 0,       -- 场均击毁
    avg_exp          FLOAT        DEFAULT 0,       -- 场均经验
    ship_cache       JSON         DEFAULT NULL,    -- 船只缓存数据

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id)
);

-- 用户 PvP 极值记录表
-- 存储用户各项战斗指标的最高记录
CREATE TABLE IF NOT EXISTS T_user_pvp_record (
    id                      INT          AUTO_INCREMENT,

    account_id              BIGINT       NOT NULL,     -- 1-11位的非连续数字
    max_exp                 INT          DEFAULT 0,    -- 最高经验
    max_exp_id              BIGINT       DEFAULT NULL, -- 最高经验船只 ID
    max_damage              INT          DEFAULT 0,    -- 最高伤害
    max_damage_id           BIGINT       DEFAULT NULL, -- 最高伤害船只 ID
    max_frags               INT          DEFAULT 0,    -- 最高击毁
    max_frags_id            BIGINT       DEFAULT NULL, -- 最高击毁船只 ID
    max_planes_killed       INT          DEFAULT 0,    -- 最高击落飞机
    max_planes_killed_id    BIGINT       DEFAULT NULL, -- 最高击落飞机船只 ID
    max_scouting_damage     INT          DEFAULT 0,    -- 最高侦查伤害
    max_scouting_damage_id  BIGINT       DEFAULT NULL, -- 最高侦查伤害船只 ID
    max_potential_damage    INT          DEFAULT 0,    -- 最高潜在伤害
    max_potential_damage_id BIGINT       DEFAULT NULL, -- 最高潜在伤害船只 ID

    created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id)
);

-- 用户配置表
-- 存储用户的个性化配置，如等级、存储限制等
CREATE TABLE IF NOT EXISTS T_user_config (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,
    user_level       TINYINT      DEFAULT 0,       -- 用户等级 0无 1普通 2高级
    storage_limit    INT          DEFAULT 0,       -- Recent 功能储存数据限制
    query_count      INT          DEFAULT 0,       -- 账号查询次数
    last_query_at    TIMESTAMP    DEFAULT NULL,    -- 上次查询时间

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_rid_aid (account_id)
);

-- 用户基础数据归档表
-- 按日期记录用户基础表的行数变化
CREATE TABLE IF NOT EXISTS ARCH_user_base (
    id               BIGINT       AUTO_INCREMENT,

    stat_date        DATE         NOT NULL,        -- 统计日期 YYYY-MM-DD
    row_count        INT          NOT NULL,        -- 当日数据条目数

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_date (stat_date)
);