import os
import json
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

if (ROOT_DIR / 'env.dev').exists():
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('Dead env file failed')

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}

file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
USER_INIT_TABLE_LIST = data['USER_INIT_TABLE_LIST']
CLAN_INIT_TABLE_LIST = data['CLAN_INIT_TABLE_LIST']

BATCH_SIZE = 10000

def maintenance_database(cursor) -> None:
    cursor.execute(f"SELECT MAX(id) FROM T_user_base;")
    max_id = cursor.fetchone()[0] or 0

    print(f'Table T_user_base MaxID: {max_id}')

    missing_ids = []
    expected_id = 1

    # 按 id 区间循环
    for start_id in range(1, max_id + 1, BATCH_SIZE):
        end_id = start_id + BATCH_SIZE - 1
        sql = """
            SELECT 
                id, 
                account_id 
            FROM T_user_base
            WHERE id BETWEEN %s AND %s
            ORDER BY id ASC;
        """
        cursor.execute(sql, [start_id, end_id])
        rows = cursor.fetchall()
        if not rows:
            # 整批都缺失
            for i in range(start_id, end_id + 1):
                missing_ids.append(i)
            expected_id = end_id + 1
            continue

        for (current_id, account_id) in rows:
            while expected_id < current_id:
                missing_ids.append(expected_id)
                expected_id += 1
            expected_id = current_id + 1

    # 输出结果
    if missing_ids:
        print(f"⚠️  发现 {len(missing_ids)} 个缺失的自增 id:")
        print(missing_ids)
    else:
        print("✅ 自增 id 完全连续，无缺失")


def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            maintenance_database(cursor)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    # python tools/check.py
    main()