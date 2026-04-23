CREATE TABLE D_activity_strategy (
    id               INT          AUTO_INCREMENT,
    user_level       TINYINT      NOT NULL DEFAULT 0,
    activity_level   TINYINT      NOT NULL,
    interval_seconds INT          NOT NULL,
    description      VARCHAR(10)  NOT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_level (user_level, activity_level)
);

CREATE TABLE D_metric_name (
    id               INT          AUTO_INCREMENT,
    name             VARCHAR(20)  NOT NULL,
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id) -- 主键
);

CREATE TABLE D_ship_type (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    -- 用户基础信息数据: name
    name             VARCHAR(20)  NOT NULL,
    -- 记录数据创建的时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id) -- 主键
);

CREATE TABLE D_ship_nation (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    -- 用户基础信息数据: name
    name             VARCHAR(20)  NOT NULL,
    -- 记录数据创建的时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id) -- 主键
);

CREATE TABLE D_ship_rarity (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    -- 用户基础信息数据: name
    name             VARCHAR(20)  NOT NULL,
    -- 记录数据创建的时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id) -- 主键
);

CREATE TABLE T_ship_base (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,    -- 1-11位的非连续数字
    -- 船只基本信息
    is_enabled       BOOLEAN      DEFAULT FALSE,
    is_old           BOOLEAN      DEFAULT FALSE,
    tier             TINYINT      DEFAULT 1,
    type_id          TINYINT      DEFAULT 1,
    nation_id        TINYINT      DEFAULT 1,
    rarity_id        TINYINT      DEFAULT NULL,
    premium          BOOLEAN      DEFAULT FALSE,
    special          BOOLEAN      DEFAULT FALSE,
    index_code       VARCHAR(50)  DEFAULT NULL,
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    INDEX idx_tier (tier),
    INDEX idx_type (type_id),
    INDEX idx_nation (nation_id),
    UNIQUE INDEX idx_sid (ship_id), -- 索引
    UNIQUE INDEX idx_rank_sid (ship_id, is_enabled, is_old, tier) 
);

CREATE TABLE T_ship_name (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,    -- 1-11位的非连续数字
    -- 船只名称
    zh_cn            VARCHAR(50)  DEFAULT NULL,
    zh_sg            VARCHAR(50)  DEFAULT NULL,
    zh_tw            VARCHAR(50)  DEFAULT NULL,
    en_short         VARCHAR(50)  DEFAULT NULL,
    en_full          VARCHAR(50)  DEFAULT NULL,
    ja               VARCHAR(50)  DEFAULT NULL,
    ru               VARCHAR(50)  DEFAULT NULL,
    verify           BOOLEAN      DEFAULT FALSE,
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_sid (ship_id) -- 索引
);

CREATE TABLE T_ship_stats_by_battles (
    -- 相关id
    id               BIGINT       AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,    -- 1-11位的非连续数字
    -- 船只基本信息
    battles          BIGINT       DEFAULT 0,
    win_rate         FLOAT        DEFAULT 0,
    avg_damage       FLOAT        DEFAULT 0,
    avg_frags        FLOAT        DEFAULT 0,
    avg_exp          FLOAT        DEFAULT 0,
    survived_rate    FLOAT        DEFAULT 0,
    avg_scouting_damage INT       DEFAULT 0,
    avg_potential_damage INT      DEFAULT 0,
    -- 记录数据的更新时间
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_sid (ship_id) -- 索引
);

CREATE TABLE T_ship_stats_by_users (
    -- 相关id
    id               BIGINT       AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,    -- 1-11位的非连续数字
    -- 船只基本信息
    users            INT          DEFAULT 0,
    battles          BIGINT       DEFAULT 0,
    win_rate         FLOAT        DEFAULT 0,
    avg_damage       FLOAT        DEFAULT 0,
    avg_frags        FLOAT        DEFAULT 0,
    avg_exp          FLOAT        DEFAULT 0,
    survived_rate    FLOAT        DEFAULT 0,
    avg_scouting_damage INT       DEFAULT 0,
    avg_potential_damage INT      DEFAULT 0,
    -- 记录数据的更新时间
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_sid (ship_id) -- 索引
);

CREATE TABLE T_ship_stats_by_recent_archive (
    id               BIGINT       AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,
    game_version     VARCHAR(10)  NOT NULL,     -- 版本号

    battles          INT          NOT NULL DEFAULT 0,
    wins             INT          NOT NULL DEFAULT 0,
    damage           BIGINT       NOT NULL DEFAULT 0,
    frags            INT          NOT NULL DEFAULT 0,
    exp              BIGINT       NOT NULL DEFAULT 0,
    survived         INT          NOT NULL DEFAULT 0,
    scouting_damage  BIGINT       NOT NULL DEFAULT 0,
    potential_damage BIGINT       NOT NULL DEFAULT 0,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_ship_version (ship_id, game_version),

    INDEX idx_version (game_version),
    INDEX idx_ship (ship_id)
);

CREATE TABLE T_ship_stats_by_battles_archive (
    id               BIGINT       AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,
    stat_date        DATE         NOT NULL,     -- YYYY-MM-DD
    game_version     VARCHAR(10)  NOT NULL,     -- 版本号

    battles          BIGINT       NOT NULL,
    win_rate         FLOAT        NOT NULL,
    avg_damage       FLOAT        NOT NULL,
    avg_frags        FLOAT        NOT NULL,
    avg_exp          FLOAT        NOT NULL,
    survived_rate    FLOAT        NOT NULL,
    avg_scouting_damage INT       NOT NULL,
    avg_potential_damage INT      NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE KEY uk_ship_date_ver (ship_id, stat_date),

    INDEX idx_ship_ver_date (ship_id, game_version),

    INDEX idx_date (stat_date),

    INDEX idx_version (game_version)
);

CREATE TABLE T_ship_stats_by_users_archive (
    id               BIGINT       AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,
    stat_date        DATE         NOT NULL,     -- YYYY-MM-DD
    game_version     VARCHAR(10)  NOT NULL,     -- 版本号

    users            INT          NOT NULL,
    battles          BIGINT       NOT NULL,
    win_rate         FLOAT        NOT NULL,
    avg_damage       FLOAT        NOT NULL,
    avg_frags        FLOAT        NOT NULL,
    avg_exp          FLOAT        NOT NULL,
    survived_rate    FLOAT        NOT NULL,
    avg_scouting_damage INT       NOT NULL,
    avg_potential_damage INT      NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE KEY uk_ship_date_ver (ship_id, stat_date, game_version),

    INDEX idx_ship_ver_date (ship_id, game_version, stat_date),

    INDEX idx_date (stat_date),

    INDEX idx_version (game_version)
);

CREATE TABLE T_ship_pvp_record (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    ship_id          BIGINT       NOT NULL,    -- 1-11位的非连续数字
    -- 船只基本信息
    exp              INT          DEFAULT 0,
    exp_users        INT          DEFAULT 0,
    exp_user_id      BIGINT       DEFAULT NULL,
    frags            INT          DEFAULT 0,
    frags_users      INT          DEFAULT 0,
    frags_user_id    BIGINT       DEFAULT NULL,
    planes           INT          DEFAULT 0,
    planes_users     INT          DEFAULT 0,
    planes_user_id   BIGINT       DEFAULT NULL,
    damage           INT          DEFAULT 0,
    damage_users     INT          DEFAULT 0,
    damage_user_id   BIGINT       DEFAULT NULL,
    scouting_damage  INT          DEFAULT 0,
    scouting_damage_users INT     DEFAULT 0,
    scouting_damage_user_id BIGINT DEFAULT NULL,
    potential_damage INT          DEFAULT 0,
    potential_damage_users INT    DEFAULT 0,
    potential_damage_user_id BIGINT DEFAULT NULL,
    
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_sid (ship_id) -- 索引
);

CREATE TABLE T_ship_pvp_leaderboard (
    account_id       BIGINT       NOT NULL,    -- 1-11位的非连续数字
    ship_id          BIGINT       NOT NULL,    -- 1-11位的非连续数字
    battles          INT          NOT NULL,
    rating           DOUBLE       NOT NULL,
    win_rate         DOUBLE       NOT NULL,
    solo_rate        DOUBLE       NOT NULL,
    avg_damage       INT          NOT NULL,
    avg_damage_level TINYINT      NOT NULL,
    avg_frags        DOUBLE       NOT NULL,
    avg_frags_level  TINYINT      NOT NULL,
    avg_exp          INT          NOT NULL,
    hit_ratio        DOUBLE       NOT NULL,
    max_exp          INT          NOT NULL,
    max_damage       INT          NOT NULL,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 主键
    UNIQUE INDEX idx_sid_and_aid (ship_id, account_id)
) 
PARTITION BY HASH (ship_id)
PARTITIONS 16; -- 使用 Hash 分区将船均匀分布在例如64个分区中

CREATE TABLE T_metric_level_thresholds (
    id               INT          AUTO_INCREMENT,
    metric_id        INT          NOT NULL,
    threshold        DOUBLE       NOT NULL,

    PRIMARY KEY (id), -- 主键

    INDEX idx_mid (metric_id), -- 索引

    CONSTRAINT fk_metric_id
        FOREIGN KEY (metric_id)
        REFERENCES D_metric_name(id)
);

CREATE TABLE T_user_base (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,    -- 1-11位的非连续数字
    -- 用户基础信息数据: name
    username         VARCHAR(25)  NOT NULL,    -- 最大25个字符，编码：utf-8
    register_time    TIMESTAMP    DEFAULT NULL,
    insignias        VARCHAR(55)  DEFAULT NULL,
    -- 已初始化table数量
    table_count      TINYINT      DEFAULT 0,
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE T_clan_base (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    clan_id          BIGINT       NOT NULL,     -- 11位的非连续数字
    -- 工会基础信息数据: tag league
    tag              VARCHAR(10)  NOT NULL,     -- 最大5个字符，编码：utf-8
    league           TINYINT      DEFAULT 5,    -- 当前段位 0紫金 1白金 2黄金 3白银 4青铜 5无
    -- 已初始化table数量
    table_count      TINYINT      DEFAULT 0,
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_cid (clan_id) -- 索引
);

CREATE TABLE T_user_stats (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 关于用户活跃的信息，用于recent/recents/用户排行榜功能
    is_enabled       BOOLEAN      DEFAULT FALSE,    -- 用于标记用户的有效性，0表示无效，1表示有效
    is_public        BOOLEAN      DEFAULT FALSE,    -- 用户是否隐藏战绩，0表示隐藏，1表示公开
    activity_level   TINYINT      DEFAULT 0,    -- 人为设置的用户活跃的等级
    total_battles    INT          DEFAULT 0,    -- 用户总场次
    pve_battles      INT          DEFAULT 0,    -- 用户随机总场次
    pvp_battles      INT          DEFAULT 0,    -- 用户随机总场次
    ranked_battles   INT          DEFAULT 0,    -- 用户排位战总场次
    rating_battles   INT          DEFAULT 0,    -- 用户评分战总场次
    karma            INT          DEFAULT 0,    -- 业力
    last_battle_at   TIMESTAMP    DEFAULT NULL, -- 用户最后战斗时间
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE T_clan_stats (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
    season           TINYINT      DEFAULT 0,
    leading_team_number TINYINT   DEFAULT NULL,
    battles_count    INT          DEFAULT 0,
    wins_count       INT          DEFAULT 0,
    public_rating    INT          DEFAULT 1100,
    league           TINYINT      DEFAULT 4,    -- 0=紫金 1=白金 2=黄金 3=白银 4=青铜
    division         TINYINT      DEFAULT 2,    -- 分段 1/2/3
    division_rating  INT          DEFAULT 0,
    longest_winning_streak INT    DEFAULT 0,
    stage_type       TINYINT      DEFAULT NULL,
    stage_battles    TINYINT      DEFAULT 0,
    stage_victories  TINYINT      DEFAULT 0,
    stage_progress   VARCHAR(5)   DEFAULT NULL,
    team_data        JSON         DEFAULT NULL,
    last_battle_at   TIMESTAMP    DEFAULT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE KEY uk_cid (clan_id),

    INDEX idx_last_battle (last_battle_at)
);

CREATE TABLE T_clan_users (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
    -- 关于工会活跃的信息，用于工会排行榜功能
    is_enabled       BOOLEAN      DEFAULT FALSE,    -- 用于标记工会的有效性，0表示无效，1表示有效
    member_count     INT          DEFAULT 0,    -- 工会玩家数量
    member_ids       JSON         DEFAULT NULL, -- 玩家ids
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_cid (clan_id) -- 索引
);

CREATE TABLE T_user_action (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 曾用名
    username         VARCHAR(25)  NOT NULL,    -- 最大25个字符，编码：utf-8
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    -- 因为数据不会更新，所以不需要updated_at，只需要created_at

    PRIMARY KEY (id), -- 主键

    INDEX idx_aid (account_id),

    INDEX idx_username (username)
);  

CREATE TABLE T_clan_action (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    -- 对局相关信息和ID
    clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    action_type      TINYINT      NOT NULL,     -- 1=加入，2=退出
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    -- 因为数据不会更新，所以不需要updated_at，只需要created_at

    PRIMARY KEY (id), -- 主键

    INDEX idx_cid (clan_id),

    INDEX idx_aid (account_id)
);  

CREATE TABLE T_user_clan (
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,       -- 1-10位的非连续数字
    clan_id          BIGINT       DEFAULT NULL,   -- 10位的非连续数字 none表示无工会
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id), -- 唯一索引

    INDEX idx_cid (clan_id) -- 非唯一索引
);

CREATE TABLE T_user_pvp (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 记录用户缓存的数据和更新时间
    battles          INT          DEFAULT 0, -- 总战斗场次
    win_rate         DOUBLE       DEFAULT 0, -- 胜率
    avg_damage       DOUBLE       DEFAULT 0, -- 场均
    avg_frags        DOUBLE       DEFAULT 0, -- 击杀
    avg_exp          DOUBLE       DEFAULT 0, -- 裸经验
    ship_cache       JSON         DEFAULT NULL, -- 缓存数据
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE T_user_pvp_record (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,     -- 1-11位的非连续数字
    -- 记录用户缓存的数据和更新时间
    max_exp          INT          DEFAULT 0,
    max_exp_id       BIGINT       DEFAULT NULL,
    max_damage       INT          DEFAULT 0,
    max_damage_id    BIGINT       DEFAULT NULL,
    max_frags        INT          DEFAULT 0,
    max_frags_id     BIGINT       DEFAULT NULL,
    max_planes_killed       INT          DEFAULT 0,
    max_planes_killed_id    BIGINT       DEFAULT NULL,
    max_scouting_damage     INT          DEFAULT 0,
    max_scouting_damage_id  BIGINT       DEFAULT NULL,
    max_potential_damage    INT          DEFAULT 0,
    max_potential_damage_id BIGINT       DEFAULT NULL,

    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE T_user_private (
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
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_aid (account_id) -- 索引
);

CREATE TABLE T_user_config (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    account_id       BIGINT       NOT NULL,
    -- 用户配置
    user_level       TINYINT      DEFAULT 0,      -- 用户等级，0-无，1-普通，2-高级
    storage_limit    INT          DEFAULT 0,      -- Recent功能储存数据限制
    query_count      INT          DEFAULT 0,      -- 账号查询次数
    last_query_at    TIMESTAMP    DEFAULT NULL,   -- 用户上次查询的时间
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id), -- 主键

    UNIQUE INDEX idx_rid_aid (account_id) -- 索引
);