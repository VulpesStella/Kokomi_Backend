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
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    CLAN_INIT_TABLE_LIST: list = data['CLAN_INIT_TABLE_LIST']

def read_clans_from_csv(filepath: Path) -> list[dict]:
    """读取CSV，返回 members_count > 0 的公会列表"""
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return []

    clans = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                members = int(row['members_count'])
                if members > 0:
                    clans.append({
                        'clan_id': int(row['clan_id']),
                        'tag': row.get('tag', 'N/A'),
                        'league': row.get('league', 5)
                    })
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return []

    logger.info(f"Loaded {len(clans)} valid clans from CSV")
    return clans

def insert_clan(cursor, clan: dict, check: bool) -> None:
    """插入一个公会"""
    clan_id = clan['clan_id']
    
    # [可选] 是否在插入前检查
    # 如果数据库为空，则可以不检查
    if check:
        cursor.execute("SELECT 1 FROM T_clan_base WHERE clan_id = %s;", [clan_id])
        if cursor.fetchone():
            return

    # 1. 插入主表
    sql = """
        INSERT INTO T_clan_base (
            clan_id, tag, league
        ) VALUES (
            %s, %s, %s
        );
    """
    cursor.execute(sql, [clan_id, clan['tag'], clan['league']])

    # 2. 为每个关联表插入 clan_id
    for table_name in CLAN_INIT_TABLE_LIST:
        sql = f"INSERT INTO {table_name} (clan_id) VALUES (%s);"
        cursor.execute(sql, [clan_id])

def main(filepath: Path, check: bool):
    """从CSV文件初始化公会相关表"""

    # 读取CSV数据
    clans = read_clans_from_csv(filepath)
    if not clans:
        logger.info("No clans to process, exiting")
        return
    
    conn = pymysql.connect(**DB_CONFIG)

    try:
        conn.begin()
        with conn.cursor() as cursor:
            with tqdm(clans, desc="Inserting clans", total=len(clans)) as pbar:
                i = 1
                for item in pbar:
                    clan_id = item['clan_id']
                    pbar.set_postfix_str(str(clan_id))

                    insert_clan(cursor, item, check)

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
    """公会数据初始化工具。
    
    从CSV文件读取 members_count > 0 的公会数据，
    初始化 T_clan_base、T_clan_users、T_clan_stats 三个表。
    
    使用示例：
    python init/insert_clan.py
    """
    filepath = ROOT_DIR / 'data/trash/clans.csv'

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
    except Exception as e:
        logger.error(e)