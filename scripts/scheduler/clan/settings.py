import os
from pathlib import Path
from datetime import datetime


CLIENT_NAME = 'SchedulerClan'
LOG_LEVEL = 'debug'
REFRESH_INTERVAL = 300
DATE_FMT = '%Y-%m-%d %H:%M:%S'

# 通过api获取season数据
# 更新SeasonID同时要创建对应的表
# https://developers.wargaming.net/reference/all/wows/clans/season/?language=en&r_realm=asia

if os.getenv('PLATFORM') is None:
    from dotenv import load_dotenv
    load_result = load_dotenv('.env.dev')
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: .env.dev")
else:
    print(f"{datetime.now().strftime(DATE_FMT)} [INIT] Env config loaded: .env.prod")

LOG_DIR = Path(os.getenv("LOG_DIR"))
DATA_DIR = Path(os.getenv("DATA_DIR"))
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD"),
    "decode_responses": True
}

'''
CREATE TABLE clan_battle_s33 (
    -- 相关id
    id               INT          AUTO_INCREMENT,
    -- 对局相关信息和ID
    battle_time      TIMESTAMP    NOT NULL,     -- 战斗时间
    region_id        TINYINT      NOT NULL,     -- 服务器id
    clan_id          BIGINT       NOT NULL,     -- 10位的非连续数字
    team_number      TINYINT      NOT NULL,     -- 队伍id
    -- 对局结果
    battle_result    VARCHAR(10)  NOT NULL,     -- 对局结果 胜利或者失败
    battle_rating    VARCHAR(10)  DEFAULT NULL, -- 对局分数 如果是晋级赛则会显示为0
    battle_stage     VARCHAR(10)  DEFAULT NULL, -- 对局结果 仅对于stage有效
    -- 对局结算的数据
    league           TINYINT      DEFAULT NULL, -- 段位 0紫金 1白金 2黄金 3白银 4青铜
    division         TINYINT      DEFAULT NULL, -- 分段 1 2 3
    division_rating  INT          DEFAULT NULL, -- 分段分数，示例：白金 1段 25分
    public_rating    INT          DEFAULT NULL, -- 工会评分 1199 - 3000
    stage_type       VARCHAR(10)  DEFAULT NULL, -- 晋级赛/保级赛 默认为Null
    stage_progress   VARCHAR(50)  DEFAULT NULL, -- 晋级赛/保级赛的当前结果
    -- 记录数据创建的时间和更新时间
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 因为数据不会更新，所以不需要updated_at，只需要created_at

    PRIMARY KEY (id), -- 主键

    INDEX idx_time (battle_time), -- 索引

    INDEX idx_cid (clan_id) -- 索引
);
'''