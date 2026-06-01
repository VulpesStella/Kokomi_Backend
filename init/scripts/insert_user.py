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

file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    USER_INIT_TABLE_LIST: list = data['USER_INIT_TABLE_LIST']

def read_users_from_csv(filepath: Path) -> list[dict]:
    """读取CSV，返回 members_count > 0 的公会列表"""
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return []

    users = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                is_enable = int(row['is_active'])
                is_public = int(row['is_public'])
                if is_enable and is_public:
                    users.append({
                        'account_id': int(row['account_id']),
                        'username': row.get('username', f"User_{row['account_id']}")
                    })
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return []

    logger.info(f"Loaded {len(users)} valid users from CSV")
    return users

def insert_user(cursor, clan: dict, check: bool) -> None:
    """插入一个用户"""
    account_id = clan['account_id']
    
    # [可选] 是否在插入前检查
    # 如果数据库为空，则可以不检查
    if check:
        cursor.execute("SELECT 1 FROM T_user_base WHERE account_id = %s;", [account_id])
        if cursor.fetchone():
            return

    # 1. 插入主表
    sql = """
        INSERT INTO T_user_base (
            account_id, username
        ) VALUES (
            %s, %s
        );
    """
    cursor.execute(sql, [account_id, clan['username']])

    # 2. 为每个关联表插入 clan_id
    for table_name in USER_INIT_TABLE_LIST:
        sql = f"INSERT INTO {table_name} (account_id) VALUES (%s);"
        cursor.execute(sql, [account_id])

def main(filepath: Path, check: bool):
    """从CSV文件初始化公会相关表"""

    # 读取CSV数据
    uses = read_users_from_csv(filepath)
    if not uses:
        logger.info("No uses to process, exiting")
        return
    
    conn = pymysql.connect(**DB_CONFIG)

    try:
        conn.begin()
        with conn.cursor() as cursor:
            with tqdm(uses, desc="Inserting uses", total=len(uses)) as pbar:
                i = 1
                for item in pbar:
                    account_id = item['account_id']
                    pbar.set_postfix_str(str(account_id))

                    insert_user(cursor, item, check)

                    # 每写入100个提交一次
                    if i % 100 == 0:
                        conn.commit()
                    i += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    
    logger.info("Initialization completed")

if __name__ == '__main__':
    """用户数据初始化工具
    
    从CSV文件读取有效的用户数据，初始化表
    
    使用示例：
    python init/scripts/insert_user.py -c 1
    """
    filepath = ROOT_DIR / 'data/trash/users.csv'

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--check",
        type=int,
        required=True,
        help="Index"
    )
    args = parser.parse_args()
    check = args.check
    if check not in [0,1]:
        raise ValueError('Incorrect code')
    
    try:
        main(filepath, check)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")