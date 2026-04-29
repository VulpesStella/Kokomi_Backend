import os
import argparse
import pymysql
from pathlib import Path
from dotenv import load_dotenv


load_dotenv('env.dev')
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}


def migrate_archive_table():
    """归档表结构迁移：保留数据，删除旧表，建新表，恢复数据（重新生成自增ID）。

    流程：
    1. 创建临时表存储旧数据（不含id）
    2. 删除旧表
    3. 创建新表（含新索引结构）
    4. 从临时表转移数据到新表
    5. 删除临时表
    """
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()
    try:
        with conn.cursor() as cursor:
            # 步骤1：备份旧表数据（不包含id字段）
            print('Step 1: Backing up old data...')
            cursor.execute("""
                CREATE TABLE ARCH_ship_stats_by_users_backup AS 
                SELECT 
                    ship_id,
                    stat_date,
                    game_version,
                    users,
                    battles,
                    win_rate,
                    avg_damage,
                    avg_frags,
                    avg_exp,
                    survived_rate,
                    avg_scouting_damage,
                    avg_potential_damage,
                    created_at
                FROM ARCH_ship_stats_by_users
            """)
            print(f'  -> Backup created: {cursor.rowcount} rows copied')

            # 步骤2：删除旧表
            print('Step 2: Dropping old table...')
            cursor.execute("DROP TABLE IF EXISTS ARCH_ship_stats_by_users")
            print('  -> Old table dropped')

            # 步骤3：创建新表（含新索引，id从1重新开始）
            print('Step 3: Creating new table...')
            cursor.execute("""
                CREATE TABLE ARCH_ship_stats_by_users (
                    id               BIGINT       AUTO_INCREMENT,
                    ship_id          BIGINT       NOT NULL,
                    stat_date        DATE         NOT NULL,
                    game_version     VARCHAR(10)  NOT NULL,

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

                    PRIMARY KEY (id),

                    UNIQUE KEY uk_ship_date_ver (ship_id, stat_date, game_version),

                    INDEX idx_version_date_desc (game_version, stat_date DESC)
                )
            """)
            print('  -> New table created')

            # 步骤4：从备份表转移数据到新表（id由MySQL自动重新生成）
            print('Step 4: Migrating data...')
            cursor.execute("""
                INSERT INTO ARCH_ship_stats_by_users (
                    ship_id, stat_date, game_version,
                    users, battles, win_rate, avg_damage, avg_frags, avg_exp,
                    survived_rate, avg_scouting_damage, avg_potential_damage,
                    created_at
                )
                SELECT 
                    ship_id,
                    stat_date,
                    game_version,
                    users,
                    battles,
                    win_rate,
                    avg_damage,
                    avg_frags,
                    avg_exp,
                    survived_rate,
                    avg_scouting_damage,
                    avg_potential_damage,
                    created_at
                FROM ARCH_ship_stats_by_users_backup
            """)
            print(f'  -> Data migrated: {cursor.rowcount} rows restored')

            # 步骤5：删除备份表
            print('Step 5: Dropping backup table...')
            cursor.execute("DROP TABLE IF EXISTS ARCH_ship_stats_by_users_backup")
            print('  -> Backup table dropped')

        conn.commit()
        print('\nSuccess: Table migration completed!')
    except Exception as e:
        conn.rollback()
        print(f'\nError: Migration failed - {e}')
        print('  -> Rolling back changes...')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    '''归档表结构迁移工具。

    用于修改 ARCH_ship_stats_by_users 的表结构（索引等），
    自动保留原始数据并完成迁移，重新生成自增ID。

    使用示例：
    python scripts/migrate_archive_table.py
    '''
    parser = argparse.ArgumentParser(description='Migrate archive table schema')
    args = parser.parse_args()
    migrate_archive_table()