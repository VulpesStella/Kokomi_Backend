SET GLOBAL TRANSACTION ISOLATION LEVEL READ COMMITTED;

CREATE DATABASE IF NOT EXISTS wows_test;

USE wows_test;

CREATE TABLE user_base (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL UNIQUE,    -- 1-11位的非连续数字
    -- 用户基础信息数据: name
    username         VARCHAR(25)  NOT NULL,    -- 最大25个字符，编码：utf-8
    register_time    TIMESTAMP    DEFAULT NULL,
    insignias        VARCHAR(55)  DEFAULT NULL,
    -- 记录数据创建的时间和更新时间
    touch_at         TIMESTAMP    DEFAULT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_rid_aid (account_id) -- 索引
);

CREATE TABLE clan_base (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    clan_id          BIGINT       NOT NULL UNIQUE,     -- 11位的非连续数字
    -- 工会基础信息数据: tag league
    tag              VARCHAR(10)  NOT NULL,     -- 最大5个字符，编码：utf-8
    league           TINYINT      DEFAULT 5,    -- 当前段位 0紫金 1白金 2黄金 3白银 4青铜 5无
    -- 记录数据创建的时间和更新时间
    touch_at         TIMESTAMP    DEFAULT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_rid_cid (clan_id) -- 索引
);

CREATE TABLE user_stats (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 关于用户活跃的信息，用于recent/recents/用户排行榜功能
    is_enabled       TINYINT      DEFAULT 0,    -- 用于标记用户的有效性，0表示无效，1表示有效
    activity_level   TINYINT      DEFAULT 0,    -- 人为设置的用户活跃的等级
    is_public        TINYINT      DEFAULT 0,    -- 用户是否隐藏战绩，0表示隐藏，1表示公开
    total_battles    INT          DEFAULT 0,    -- 用户总场次
    pvp_battles      INT          DEFAULT 0,    -- 用户随机总场次
    ranked_battles   INT          DEFAULT 0,    -- 用户排位/评分战总场次
    last_battle_at   TIMESTAMP    DEFAULT NULL, -- 用户最后战斗时间
    -- 记录数据创建的时间和更新时间
    touch_at         TIMESTAMP    DEFAULT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE clan_users (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
    -- 关于工会活跃的信息，用于工会排行榜功能
    is_enabled       TINYINT      DEFAULT 0,    -- 用于标记工会的有效性，0表示无效，1表示有效
    member_count     INT          DEFAULT 0,    -- 工会玩家数量
    member_ids       JSON         DEFAULT NULL, -- 玩家ids
    -- 记录数据创建的时间和更新时间
    touch_at         TIMESTAMP    DEFAULT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_cid (clan_id) -- 索引
);

CREATE TABLE clan_action (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    -- 对局相关信息和ID
    clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    action_type      TINYINT      NOT NULL,     -- 1=加入，2=退出
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 因为数据不会更新，所以不需要updated_at，只需要created_at

    PRIMARY KEY (id), -- 主键

    INDEX idx_clan_time (clan_id, created_at),

    INDEX idx_account_time (account_id, created_at)
);  

CREATE TABLE user_clan (
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,       -- 1-10位的非连续数字
    clan_id          BIGINT       DEFAULT NULL,   -- 10位的非连续数字 none表示无工会
    -- 记录数据创建的时间和更新时间
    touch_at         TIMESTAMP    DEFAULT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id), -- 唯一索引

    INDEX idx_cid (clan_id) -- 非唯一索引
);

CREATE TABLE user_cache (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 记录用户缓存的数据和更新时间
    pvp_count        INT          DEFAULT 0, -- 总战斗场次
    win_rate         DOUBLE       DEFAULT 0, -- 胜率
    avg_damage       DOUBLE       DEFAULT 0, -- 场均
    avg_frags        DOUBLE       DEFAULT 0, -- 击杀
    max_damage       INT          DEFAULT 0, -- 个人最高伤害
    max_damage_id    BIGINT       DEFAULT NULL, -- 个人最高伤害对应的船只
    max_exp          INT          DEFAULT 0, -- 个人最高经验
    max_exp_id       BIGINT       DEFAULT NULL, -- 个人最高经验对应的船只
    cache            BLOB         DEFAULT NULL, -- 压缩处理后的缓存数据
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE user_private (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 记录用户缓存的数据和更新时间
    update_date      VARCHAR(10)  DEFAULT NULL,
    battles          INT          DEFAULT 0,
    life_time        BIGINT       DEFAULT 0,
    distance         INT          DEFAULT 0,
    gold             INT          DEFAULT 0,
    free_xp          BIGINT       DEFAULT 0,
    credits          BIGINT       DEFAULT 0,
    slots            INT          DEFAULT 0,
    port             JSON         DEFAULT NULL,
    achieve          JSON         DEFAULT NULL,
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE recent (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,
    -- 用户配置
    enable_recent    TINYINT      DEFAULT 0,      -- 是否启用recent功能
    enable_daily     TINYINT      DEFAULT 0,      -- 是否启用recents功能
    recent_limit     INT          DEFAULT 0,      -- recent功能储存数据上限
    last_query_at    TIMESTAMP    DEFAULT NULL,   -- 用户上次查询的时间
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_rid_aid (account_id) -- 索引
);