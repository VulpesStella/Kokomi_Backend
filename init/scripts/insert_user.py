import os
import csv
import json
import logging
import pymysql
import argparse
from tqdm import tqdm
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
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

# 分批大小
BATCH_SIZE = 10_000

# 读取常量配置
file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    USER_INIT_TABLE_LIST: list = data['USER_INIT_TABLE_LIST']


def read_users_from_csv(filepath: Path) -> list[dict]:
    """读取CSV，返回全部用户列表（保持文件顺序）"""
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return []

    users = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                users.append({
                    'account_id': int(row['account_id']),
                    'username': row.get('username', f"User_{row['account_id']}")
                })
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return []

    logger.info(f"Loaded {len(users)} users from CSV")
    return users


def main(filepath: Path):
    """从CSV文件批量初始化用户相关表（每表分批插入，一个事务）"""
    users = read_users_from_csv(filepath)
    if not users:
        logger.info("No users to process, exiting")
        return

    # 准备数据，保持顺序
    base_data = [(u['account_id'], u['username']) for u in users]
    account_ids = [[u['account_id']] for u in users]

    conn = pymysql.connect(**DB_CONFIG)

    try:
        # 写入主表 T_user_base
        sql_base = "INSERT INTO T_user_base (account_id, username) VALUES (%s, %s)"
        with conn.cursor() as cursor:
            batches = range(0, len(base_data), BATCH_SIZE)
            for i in tqdm(batches, desc="Inserting T_user_base", unit="batch"):
                batch = base_data[i:i + BATCH_SIZE]
                cursor.executemany(sql_base, batch)
        conn.commit()
        logger.info(f"Inserted {len(users)} rows into T_user_base")

        # 逐个写入关联表
        for table_name in USER_INIT_TABLE_LIST:
            sql = f"INSERT INTO {table_name} (account_id) VALUES (%s)"
            with conn.cursor() as cursor:
                batches = range(0, len(account_ids), BATCH_SIZE)
                for i in tqdm(batches, desc=f"Inserting {table_name}", unit="batch"):
                    batch = account_ids[i:i + BATCH_SIZE]
                    cursor.executemany(sql, batch)
            conn.commit()
            logger.info(f"Inserted {len(users)} rows into {table_name}")
    except Exception:
        conn.rollback()
        logger.exception("Insertion failed, rolled back")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """用户数据初始化工具
    
    使用示例：
    python init/scripts/insert_user.py
    python init/scripts/insert_user.py -f users_1
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=str, help="CSV file name")
    args = parser.parse_args()
    
    if args.file:
        default_csv = ROOT_DIR / 'data/trash' / f'{args.file}.csv'
    else:
        default_csv = ROOT_DIR / 'data/trash' / 'users.csv'

    try:
        main(default_csv)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")