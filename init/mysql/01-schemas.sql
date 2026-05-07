-- ============================================================
-- D_ 前缀：字典表 / 维度表，存储业务枚举值
-- ============================================================

-- 活动策略配置表
-- 定义不同用户等级在各级活跃度下的数据拉取间隔
CREATE TABLE IF NOT EXISTS D_user_activity_strategy (
    id               INT          AUTO_INCREMENT,

    user_level       TINYINT      NOT NULL DEFAULT 0,
    activity_level   TINYINT      NOT NULL,
    interval_seconds INT          NOT NULL,
    description      VARCHAR(10)  NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),

    UNIQUE INDEX idx_level (user_level, activity_level)
);

-- 活动策略配置表
-- 定义不同工会等级在各级活跃度下的数据拉取间隔
CREATE TABLE IF NOT EXISTS D_clan_activity_strategy (
    id               INT          AUTO_INCREMENT,

    clan_level       TINYINT      NOT NULL DEFAULT 0,
    activity_level   TINYINT      NOT NULL,
    interval_seconds INT          NOT NULL,
    description      VARCHAR(10)  NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),

    UNIQUE INDEX idx_level (clan_level, activity_level)
);

-- 指标名称字典表
-- 存储用户 PvP 记录中各项指标的名称，如 max_exp、max_damage 等
CREATE TABLE IF NOT EXISTS D_metric_name (
    id               INT          AUTO_INCREMENT,

    name             VARCHAR(20)  NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id)
);

-- 排行榜场次限制字典表
-- 定义各等级船只上榜所需的最小战斗场次
CREATE TABLE IF NOT EXISTS D_ranking_battles_limit (
    id               INT          AUTO_INCREMENT,

    tier             INT          NOT NULL,      -- 船只等级
    battles_limit    INT          NOT NULL,      -- 场次限制

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_tier (tier)
);

-- 船只类型字典表
-- 存储船只类型名称
CREATE TABLE IF NOT EXISTS D_ship_type (
    id               INT          AUTO_INCREMENT,

    name             VARCHAR(20)  NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id)
);

-- 船只国家字典表
-- 存储船只所属国家名称
CREATE TABLE IF NOT EXISTS D_ship_nation (
    id               INT          AUTO_INCREMENT,

    name             VARCHAR(20)  NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id)
);

-- 船只稀有度字典表
-- 存储船只稀有度名称
CREATE TABLE IF NOT EXISTS D_ship_rarity (
    id               INT          AUTO_INCREMENT,

    name             VARCHAR(20)  NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id)
);


-- ============================================================
-- T_ 前缀：事务表 / 核心业务表，存储主要业务数据
-- ============================================================

-- 游戏版本表
-- 记录各游戏版本的名称和是否为最新版本
CREATE TABLE IF NOT EXISTS T_game_version (
    id               INT          AUTO_INCREMENT,

    is_latest        BOOLEAN      DEFAULT FALSE,
    short_name       VARCHAR(10)  NOT NULL,
    full_name        VARCHAR(100) NOT NULL,

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_name (short_name)
);

-- 数据追踪元信息表
-- 记录各类数据更新任务的上次执行时间，用于判断是否需要重新执行
CREATE TABLE IF NOT EXISTS T_tracking_meta (
    id              INT           AUTO_INCREMENT,

    tracking_key    VARCHAR(50)   NOT NULL,         -- 跟踪键，如 clan、ship 等
    tracking_type   VARCHAR(20)   NOT NULL,         -- 类型：refresh_time / update_time / archive_time
    tracking_value  TIMESTAMP     DEFAULT NULL,     -- 上次执行的时间戳

    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_key_type (tracking_key, tracking_type)
);

-- 表数据量元信息表
-- 记录各业务表的数据行数，用于监控数据增长
CREATE TABLE IF NOT EXISTS T_table_meta (
    id              INT           AUTO_INCREMENT,

    metric_key      VARCHAR(50)   NOT NULL,         -- 统计键，通常为表名
    metric_value    BIGINT        DEFAULT 0,        -- 数据行数
    table_name      VARCHAR(50)   NOT NULL,         -- 数据来源表名

    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_key (metric_key)
);

-- 船只基础信息表
-- 存储船只的基本属性，包括等级、类型、国籍、稀有度等
CREATE TABLE IF NOT EXISTS T_ship_base (
    id               INT          AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,         -- 1-11位的非连续数字
    is_enabled       BOOLEAN      DEFAULT FALSE,    -- 是否启用统计
    is_old           BOOLEAN      DEFAULT FALSE,    -- 是否为旧船
    tier             TINYINT      DEFAULT 1,        -- 船只等级 1-11
    type_id          TINYINT      DEFAULT 1,        -- 船只类型 ID
    nation_id        TINYINT      DEFAULT 1,        -- 国家 ID
    rarity_id        TINYINT      DEFAULT NULL,     -- 稀有度 ID
    premium          BOOLEAN      DEFAULT FALSE,    -- 是否为金币船
    special          BOOLEAN      DEFAULT FALSE,    -- 是否为特种船
    index_code       VARCHAR(50)  DEFAULT NULL,     -- 索引代码

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_tier (tier),
    INDEX idx_type (type_id),
    INDEX idx_nation (nation_id),
    UNIQUE INDEX idx_sid (ship_id),
    UNIQUE INDEX idx_rank_sid (is_enabled, is_old, tier, ship_id)
);

-- 船只名称表
-- 存储船只的多语言名称
CREATE TABLE IF NOT EXISTS T_ship_name (
    id               INT          AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,         -- 1-11位的非连续数字
    zh_cn            VARCHAR(50)  DEFAULT NULL,     -- 简体中文名
    zh_sg            VARCHAR(50)  DEFAULT NULL,     -- 中文新加坡名
    zh_tw            VARCHAR(50)  DEFAULT NULL,     -- 繁体中文名
    en_short         VARCHAR(50)  DEFAULT NULL,     -- 英文简称
    en_full          VARCHAR(50)  DEFAULT NULL,     -- 英文全称
    ja               VARCHAR(50)  DEFAULT NULL,     -- 日文名
    ru               VARCHAR(50)  DEFAULT NULL,     -- 俄文名
    verify           BOOLEAN      DEFAULT FALSE,    -- 是否已验证

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_sid (ship_id)
);

-- 船只服务器场次统计表
-- 存储基于所有用户战斗场次计算的服务器平均数据
CREATE TABLE IF NOT EXISTS T_ship_stats_by_battles (
    id               BIGINT       AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,         -- 1-11位的非连续数字
    battles          BIGINT       DEFAULT 0,        -- 总战斗场次
    win_rate         FLOAT        DEFAULT 0,        -- 胜率（%）
    avg_damage       FLOAT        DEFAULT 0,        -- 场均伤害
    avg_frags        FLOAT        DEFAULT 0,        -- 场均击毁
    avg_exp          FLOAT        DEFAULT 0,        -- 场均经验
    survived_rate    FLOAT        DEFAULT 0,        -- 存活率（%）
    avg_scouting_damage INT       DEFAULT 0,        -- 场均侦查伤害
    avg_potential_damage INT      DEFAULT 0,        -- 场均潜在伤害

    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_sid (ship_id)
);

-- 船只用户维度统计表
-- 存储基于有效用户（battles > 10）计算的用户平均水平
CREATE TABLE IF NOT EXISTS T_ship_stats_by_users (
    id               BIGINT       AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,         -- 1-11位的非连续数字
    users            INT          DEFAULT 0,        -- 有效用户数
    battles          BIGINT       DEFAULT 0,        -- 总战斗场次
    rating           INT          DEFAULT -1,       -- 用户平均 Rating
    win_rate         FLOAT        DEFAULT 0,        -- 用户平均胜率（%）
    avg_damage       FLOAT        DEFAULT 0,        -- 用户平均场均伤害
    avg_frags        FLOAT        DEFAULT 0,        -- 用户平均场均击毁
    avg_exp          FLOAT        DEFAULT 0,        -- 用户平均场均经验
    survived_rate    FLOAT        DEFAULT 0,        -- 用户平均存活率（%）
    avg_scouting_damage INT       DEFAULT 0,        -- 用户平均场均侦查伤害
    avg_potential_damage INT      DEFAULT 0,        -- 用户平均场均潜在伤害

    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_sid (ship_id)
);

-- 船只 Rating 分布统计表
-- 存储各船只用户 Rating 的百分位分布数据
CREATE TABLE IF NOT EXISTS T_ship_rating_distribution (
    id               BIGINT       AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,
    sample_count     INT          NOT NULL DEFAULT 0,   -- 样本数量
    top1             FLOAT        NOT NULL DEFAULT 0.0, -- 前1%阈值
    top5             FLOAT        NOT NULL DEFAULT 0.0, -- 前5%阈值
    top10            FLOAT        NOT NULL DEFAULT 0.0, -- 前10%阈值
    top15            FLOAT        NOT NULL DEFAULT 0.0, -- 前15%阈值
    top50            FLOAT        NOT NULL DEFAULT 0.0, -- 中位数
    top75            FLOAT        NOT NULL DEFAULT 0.0, -- 前75%阈值
    top90            FLOAT        NOT NULL DEFAULT 0.0, -- 前90%阈值

    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_ship (ship_id)
);

-- 船只 PvP 极值记录表
-- 存储各船只各项指标的最高记录及达成用户
CREATE TABLE IF NOT EXISTS T_ship_pvp_record (
    id               INT          AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,        -- 1-11位的非连续数字
    metric_id        INT          NOT NULL,        -- 关联 D_metric_name
    metric_value     INT          DEFAULT 0,       -- 指标最高值
    users_count      INT          DEFAULT 0,       -- 到达该值的用户数
    top_user_ids     JSON         DEFAULT NULL,    -- 记录此指标最高的用户ID集合

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_sid_mid (ship_id, metric_id)
);

-- 船只 PvP 排行榜表
-- 存储玩家在各船只上的战斗表现，按 Rating 排名
CREATE TABLE IF NOT EXISTS T_ship_pvp_leaderboard (
    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    ship_id          BIGINT       NOT NULL,        -- 1-11位的非连续数字

    battles          INT          NOT NULL,        -- 战斗场次
    rating           FLOAT        NOT NULL,        -- 综合评分
    win_rate         FLOAT        NOT NULL,        -- 胜率
    solo_rate        FLOAT        NOT NULL,        -- 单野率
    avg_damage       INT          NOT NULL,        -- 场均伤害
    avg_damage_level TINYINT      NOT NULL,        -- 伤害等级 1-5
    avg_frags        FLOAT        NOT NULL,        -- 场均击毁
    avg_frags_level  TINYINT      NOT NULL,        -- 击毁等级 1-5
    avg_exp          INT          NOT NULL,        -- 场均经验
    hit_ratio        FLOAT        NOT NULL,        -- 命中率
    max_exp          INT          NOT NULL,        -- 最高经验
    max_damage       INT          NOT NULL,        -- 最高伤害

    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (ship_id, account_id)
)
PARTITION BY HASH (ship_id)
PARTITIONS 16;

-- 指标等级阈值表
-- 定义各项指标等级评定的阈值，用于 F_get_metric_level 函数
CREATE TABLE IF NOT EXISTS T_metric_level_thresholds (
    id               INT          AUTO_INCREMENT,

    metric_id        INT          NOT NULL,        -- 指标 ID
    threshold        FLOAT        NOT NULL,        -- 阈值

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_mid (metric_id)
);

-- 用户基础信息表
-- 存储用户的基本信息，包括用户名、注册时间等
CREATE TABLE IF NOT EXISTS T_user_base (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    username         VARCHAR(25)  NOT NULL,        -- 最大25个字符
    register_time    TIMESTAMP    DEFAULT NULL,    -- 注册时间
    insignias        VARCHAR(55)  DEFAULT NULL,    -- 徽章信息
    table_count      TINYINT      DEFAULT 0,       -- 已初始化关联表数量

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id)
);

-- 公会基础信息表
-- 存储公会的基本信息，包括标签和段位
CREATE TABLE IF NOT EXISTS T_clan_base (
    id               INT          AUTO_INCREMENT,

    clan_id          BIGINT       NOT NULL,        -- 10位的非连续数字
    tag              VARCHAR(10)  NOT NULL,        -- 公会标签
    league           TINYINT      DEFAULT 5,       -- 当前段位 0紫金 1白金 2黄金 3白银 4青铜 5无
    table_count      TINYINT      DEFAULT 0,       -- 已初始化关联表数量

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_cid (clan_id)
);

-- 用户统计表
-- 存储用户的活跃度和战斗统计数据
CREATE TABLE IF NOT EXISTS T_user_stats (
    id               INT          AUTO_INCREMENT,

    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    is_enabled       BOOLEAN      DEFAULT FALSE,   -- 用户是否有效
    is_public        BOOLEAN      DEFAULT FALSE,   -- 用户是否公开战绩
    activity_level   TINYINT      DEFAULT 0,       -- 用户活跃等级
    total_battles    INT          DEFAULT 0,       -- 总战斗场次
    pve_battles      INT          DEFAULT 0,       -- PvE 场次
    pvp_battles      INT          DEFAULT 0,       -- PvP 场次
    ranked_battles   INT          DEFAULT 0,       -- 排位战场次
    rating_battles   INT          DEFAULT 0,       -- 评分战场次
    karma            INT          DEFAULT 0,       -- 业力值
    last_battle_at   TIMESTAMP    DEFAULT NULL,    -- 最后战斗时间

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_aid (account_id)
);

-- 公会统计表
-- 存储公会的赛季战斗统计数据
CREATE TABLE IF NOT EXISTS T_clan_stats (
    id               INT          AUTO_INCREMENT,

    clan_id          BIGINT       NOT NULL,        -- 10位的非连续数字
    season           TINYINT      DEFAULT 0,       -- 赛季 ID
    leading_team_number TINYINT   DEFAULT NULL,    -- 主力队伍编号
    battles_count    INT          DEFAULT 0,       -- 战斗总数
    wins_count       INT          DEFAULT 0,       -- 胜场数
    public_rating    INT          DEFAULT 1100,    -- 公开评分
    league           TINYINT      DEFAULT 4,       -- 段位 0紫金 1白金 2黄金 3白银 4青铜
    division         TINYINT      DEFAULT 2,       -- 分段 1/2/3
    division_rating  INT          DEFAULT 0,       -- 分段评分
    longest_winning_streak INT    DEFAULT 0,       -- 最长连胜
    stage_type       TINYINT      DEFAULT NULL,    -- 晋级赛类型
    stage_battles    TINYINT      DEFAULT 0,       -- 晋级赛场次
    stage_victories  TINYINT      DEFAULT 0,       -- 晋级赛胜场
    stage_progress   VARCHAR(5)   DEFAULT NULL,    -- 晋级赛进度
    team_data        JSON         DEFAULT NULL,    -- 队伍数据 JSON
    last_battle_at   TIMESTAMP    DEFAULT NULL,    -- 最后战斗时间

    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE KEY uk_cid (clan_id),

    INDEX idx_last_battle (last_battle_at)
);

-- 公会成员表
-- 存储公会成员数量和成员 ID 列表
CREATE TABLE IF NOT EXISTS T_clan_users (
    id               INT          AUTO_INCREMENT,

    clan_id          BIGINT       NOT NULL,        -- 10位的非连续数字
    is_enabled       BOOLEAN      DEFAULT FALSE,   -- 工会是否有效
    member_count     INT          DEFAULT 0,       -- 成员数量
    member_ids       JSON         DEFAULT NULL,    -- 成员 ID 列表

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_cid (clan_id)
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

-- 公会行为记录表
-- 记录成员加入和退出公会的历史，只追加不更新
CREATE TABLE IF NOT EXISTS T_clan_action (
    id               INT          AUTO_INCREMENT,

    clan_id          BIGINT       NOT NULL,        -- 10位的非连续数字
    account_id       BIGINT       NOT NULL,        -- 1-11位的非连续数字
    action_type      TINYINT      NOT NULL,        -- 1=加入，2=退出

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_cid (clan_id),
    INDEX idx_aid (account_id)
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


-- ============================================================
-- ARCH_ 前缀：归档表，存储历史快照数据
-- ============================================================

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

-- 公会基础数据归档表
-- 按日期记录公会基础表的行数变化
CREATE TABLE IF NOT EXISTS ARCH_clan_base (
    id               BIGINT       AUTO_INCREMENT,

    stat_date        DATE         NOT NULL,        -- 统计日期 YYYY-MM-DD
    row_count        INT          NOT NULL,        -- 当日数据条目数

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_date (stat_date)
);

-- 船只 Recent 数据归档表
-- 按版本号归档从 Recent API 拉取的船只战斗原始数据
CREATE TABLE IF NOT EXISTS ARCH_ship_stats_by_recent (
    id               BIGINT       AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,
    game_version     VARCHAR(10)  NOT NULL,        -- 游戏版本号
    battles          INT          NOT NULL DEFAULT 0,
    wins             INT          NOT NULL DEFAULT 0,
    damage           BIGINT       NOT NULL DEFAULT 0,
    frags            INT          NOT NULL DEFAULT 0,
    exp              BIGINT       NOT NULL DEFAULT 0,
    survived         INT          NOT NULL DEFAULT 0,
    scouting_damage  BIGINT       NOT NULL DEFAULT 0,
    potential_damage BIGINT       NOT NULL DEFAULT 0,

    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_ship_version (ship_id, game_version),

    INDEX idx_version (game_version),
    INDEX idx_ship (ship_id)
);

-- 船只场次统计归档表
-- 按日期和版本号归档船只的服务器场次平均数据
CREATE TABLE IF NOT EXISTS ARCH_ship_stats_by_battles (
    id               BIGINT       AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,
    stat_date        DATE         NOT NULL,        -- 统计日期 YYYY-MM-DD
    game_version     VARCHAR(10)  NOT NULL,        -- 游戏版本号
    battles          BIGINT       NOT NULL,
    win_rate         FLOAT        NOT NULL,
    avg_damage       FLOAT        NOT NULL,
    avg_frags        FLOAT        NOT NULL,
    avg_exp          FLOAT        NOT NULL,
    survived_rate    FLOAT        NOT NULL,
    avg_scouting_damage INT       NOT NULL,
    avg_potential_damage INT      NOT NULL,

    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_ship_date_ver (ship_id, stat_date, game_version),

    INDEX idx_ver_date_desc (game_version, stat_date DESC)
);

-- 船只用户统计归档表
-- 按日期和版本号归档船只的用户维度平均数据
CREATE TABLE IF NOT EXISTS ARCH_ship_stats_by_users (
    id               BIGINT       AUTO_INCREMENT,

    ship_id          BIGINT       NOT NULL,
    stat_date        DATE         NOT NULL,        -- 统计日期 YYYY-MM-DD
    game_version     VARCHAR(10)  NOT NULL,        -- 游戏版本号
    users            INT          NOT NULL,
    battles          BIGINT       NOT NULL,
    win_rate         FLOAT        NOT NULL,
    avg_damage       FLOAT        NOT NULL,
    avg_frags        FLOAT        NOT NULL,
    avg_exp          FLOAT        NOT NULL,
    survived_rate    FLOAT        NOT NULL,
    avg_scouting_damage INT       NOT NULL,
    avg_potential_damage INT      NOT NULL,

    updated_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_ship_date_ver (ship_id, stat_date, game_version),

    INDEX idx_ver_date_desc (game_version, stat_date DESC)
);


-- ============================================================
-- STAGING_ 前缀：暂存表，存储待处理的临时数据
-- ============================================================

-- 船只 Recent 数据暂存表
-- 从 API 拉取的原始数据先写入此表，再由后台任务消费处理
CREATE TABLE IF NOT EXISTS STAGING_ship_recent_data (
    uuid            CHAR(36)     NOT NULL,          -- 唯一标识

    status          ENUM('pending','done') DEFAULT 'pending',  -- 处理状态
    game_version    VARCHAR(10)  NOT NULL,          -- 游戏版本号
    account_id      BIGINT       NOT NULL,          -- 用户 ID
    payload         JSON         NOT NULL,          -- 原始数据

    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    processed_at    TIMESTAMP    DEFAULT NULL,      -- 处理完成时间

    PRIMARY KEY (uuid),

    KEY idx_consumer (status, created_at)
);