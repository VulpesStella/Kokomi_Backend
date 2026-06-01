import os
import csv
import logging
import pymysql
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
    "host": '129.226.90.10',
    "port": 3306,
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": 'kokomi',
    'autocommit': True
}

CSV_FIELDS = ['account_id', 'username', 'is_active', 'is_public']

def main(output: Path):
    """读取所有 account_id 并写入 JSON 文件"""
    conn: pymysql.connect = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 先获取最大 id
            cursor.execute("SELECT MAX(id) FROM user_basic WHERE region_id = 1;")
            max_id = cursor.fetchone()[0] or 0
            logger.info(f"Max ID: {max_id}")

            if max_id == 0:
                logger.warning("No data found")
                rows = []
            else:
                rows = []
                with tqdm(total=max_id, desc="Fetching users", unit="rows") as pbar:
                    for start_id in range(1, max_id + 1, 10000):
                        end_id = start_id + 10000 - 1

                        sql = """
                            SELECT 
                                b.account_id, 
                                b.username, 
                                i.is_active, 
                                i.is_public 
                            FROM user_basic b
                            LEFT JOIN user_info i
                            ON b.account_id = i.account_id
                            WHERE b.region_id = 1 
                            AND b.id BETWEEN %s AND %s
                            ORDER BY b.id;
                        """
                        cursor.execute(sql, [start_id, end_id])
                        batch_rows = cursor.fetchall()
                        rows.extend(batch_rows)
                        pbar.update(end_id - start_id + 1)

            logger.info(f"Fetched {len(rows)} rows")

        with open(output, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    'account_id': row[0],
                    'username': row[1],
                    'is_active': row[2],
                    'is_public': row[3]
                })
        
        logger.info(f"Saved account IDs to {output}")
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
    output = ROOT_DIR / 'data/trash/users.csv'
    try:
        main(output)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)