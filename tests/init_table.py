import os
import argparse
import pymysql
from dotenv import load_dotenv

load_dotenv('env.dev')

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}


def sync_table(mode: str, table_name: str):
    """
    mode: user / clan
    table_name: 目标表（已创建，且为空）
    """

    if mode not in ("user", "clan"):
        raise ValueError("mode must be 'user' or 'clan'")
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()
    try:
        with conn.cursor() as cursor:
            if mode == "user":
                source_table = "T_user_base"
                id_field = "account_id"
            else:
                source_table = "T_clan_users"
                id_field = "clan_id"
            insert_sql = f"""
                INSERT INTO {table_name} ({id_field})
                SELECT {id_field}
                FROM {source_table}
                ORDER BY id ASC;
            """
            cursor.execute(insert_sql)
        conn.commit()
        print(f"Success: {table_name}")

    except Exception as e:
        conn.rollback()
        print("Error:", e)
    finally:
        conn.close()


if __name__ == '__main__':
    """
    用于在本地开发环境中，对新加入的Table进行数据库数据同步。

    注意：
    - 仅限空数据表可用
    - 写入过程中不允许有新用户/工会插入

    使用示例：
    python tests/init_table.py -m user -t T_user_config
    python tests/init_table.py -m clan -t T_clan_stats
    """

    # 仅允许在 Windows 环境执行
    if os.name != 'nt':
        print("❌ This script can only be run on Windows environment.")
        exit(1)

    parser = argparse.ArgumentParser(description="Sync table id from base table")
    parser.add_argument("-m", "--mode", required=True, choices=["user", "clan"], help="user or clan")
    parser.add_argument("-t", "--table", required=True, help="target table name")

    args = parser.parse_args()

    sync_table(args.mode, args.table)