import os
import csv
import json
import logging
import pymysql
import argparse
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

# 读取常量配置
file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    CLAN_INIT_TABLE_LIST: list = data['CLAN_INIT_TABLE_LIST']


def read_clans_from_csv(filepath: Path) -> list[dict]:
    """读取CSV，返回全部公会列表（顺序与文件一致）"""
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return []

    clans = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                clans.append({
                    'clan_id': int(row['clan_id']),
                    'tag': row.get('tag', 'N/A')
                })
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return []

    logger.info(f"Loaded {len(clans)} clans from CSV")
    return clans


def main(filepath: Path):
    """从CSV文件批量初始化所有公会相关表"""
    clans = read_clans_from_csv(filepath)
    if not clans:
        logger.info("No clans to process, exiting")
        return

    # 准备主表数据
    base_data = [(c['clan_id'], c['tag']) for c in clans]
    # 关联表只需要clan_id列表
    clan_ids = [[c['clan_id']] for c in clans]

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 批量写入主表
            sql_base = "INSERT INTO T_clan_base (clan_id, tag) VALUES (%s, %s)"
            cursor.executemany(sql_base, base_data)
            conn.commit()
            logger.info(f"Inserted {len(clans)} rows into T_clan_base")

            # 批量写入所有关联表
            for table_name in CLAN_INIT_TABLE_LIST:
                sql = f"INSERT INTO {table_name} (clan_id) VALUES (%s)"
                cursor.executemany(sql, clan_ids)
                conn.commit()
                logger.info(f"Inserted {len(clans)} rows into {table_name}")
    except Exception:
        conn.rollback()
        logger.exception("Insertion failed, rolled back")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """公会数据初始化工具
    
    使用示例：
        python init/scripts/insert_clan.py
        python init/scripts/insert_clan.py -f clans_1
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=str, help="CSV file name")
    args = parser.parse_args()
    
    if args.file:
        default_csv = ROOT_DIR / 'data/trash' / f'{args.file}.csv'
    else:
        default_csv = ROOT_DIR / 'data/trash' / 'clans.csv'

    try:
        main(default_csv)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")