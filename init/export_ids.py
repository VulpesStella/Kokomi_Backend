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
    logger.info('Loading environment file: env.dev')
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    logger.info('Loading environment file: env.prod')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DB_CONFIG = {
    "host": 'localhost',
    "port": 3306,
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": 'kokomi',
    'autocommit': True
}

def main(filepath: Path):
    """读取所有 account_id 并写入 JSON 文件"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT account_id FROM user_basic WHERE region_id = 4 ORDER BY id;")
            rows = cursor.fetchall()
            # 提取整数列表
            account_ids = [row[0] for row in rows]
        logger.info(f"Fetched {len(account_ids)} account IDs")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(account_ids, f, ensure_ascii=False)
        
        logger.info(f"Saved account IDs to {filepath}")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    """导出数据库

    使用示例：
    python init\export_ids.py
    """
    filepath = ROOT_DIR / 'data/trash/users.json'
    try:
        main(filepath)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)