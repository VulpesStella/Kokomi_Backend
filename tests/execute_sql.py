import os
import logging
import pymysql
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

# 加载环境变量
if (ROOT_DIR / 'env.dev').exists():
    logger.info('Loading environment file: env.dev')
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    logger.info('Loading environment file: env.prod')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

sql = """
CREATE TABLE T_user_activity (
    id               INT          AUTO_INCREMENT,

    user_level       TINYINT      NOT NULL,        -- 用户活跃等级
    user_count       INT          DEFAULT 0,       -- 用户活跃等级

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_level (user_level)
);
CREATE TABLE T_clan_activity (
    id               INT          AUTO_INCREMENT,

    clan_level       TINYINT      NOT NULL,        -- 工会活跃等级
    clan_count       INT          DEFAULT 0,       -- 工会数量

    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE INDEX idx_level (clan_level)
);
INSERT INTO T_user_activity
    (user_level)
VALUES
    (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);
INSERT INTO T_clan_activity
    (clan_level)
VALUES
    (0),(1),(2),(3);
DROP VIEW V_user_activity_distribution;
DROP VIEW V_clan_league_distribution;
"""

def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        with conn.cursor() as cursor:
            for stmt in statements:
                cursor.execute(stmt)

        conn.commit()
        logger.info("Execute successfully")
    except Exception:
        conn.rollback()
        logger.exception("Execute failed, rolled back")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """执行 sql 语句
    
    使用示例：
    python tests/execute_sql.py
    """

    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")