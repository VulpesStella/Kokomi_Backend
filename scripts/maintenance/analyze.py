import os
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
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}

def analyze_sqlite_files() -> tuple:
    """递归扫描 db 目录下的所有 .db 文件，统计数量与总大小，并将结果写入 JSON"""
    logger.info('Analyzing SQLite3 Files...')

    db_files_dir = ROOT_DIR / 'data/db'
    # 递归查找所有 .db 文件
    db_files = list(db_files_dir.rglob("*.db"))
    file_count = len(db_files)
    total_size_kb = 0

    # 累加每个文件的大小，忽略无法读取的文件
    with tqdm(total=file_count, desc=f"Reading file szie", unit="file") as pbar:
        for f in db_files:
            try:
                total_size_kb += f.stat().st_size // 1024
            except Exception:
                continue
            pbar.update()

    avg_size_kb = total_size_kb // file_count
    if total_size_kb // 1024 // 1024 != 0:
        total_size_gb = round(total_size_kb / 1024 / 1024, 2)
    else:
        total_size_gb = '< 1'

    logger.info(
        f"Files: {file_count}  "
        f"Size: {total_size_gb} GB  "
        f"Avg: {avg_size_kb} KB"
    )
    return file_count, total_size_kb

def anaylyze_mysql_tables(cursor) -> tuple:
    cursor.execute("""
        SELECT 
            table_name
        FROM information_schema.tables
        WHERE table_schema = DATABASE();
    """)

    tables = []
    table_count = 0
    total_rows = 0
    for row in cursor.fetchall():
        # 排除 view
        if row[0].startswith(('V_','_V_')):
            continue
        table_count += 1
        tables.append(row[0])
    with tqdm(total=len(tables), desc=f"Analyze table", unit="table") as pbar:
        for table in tables:
            sql = f"ANALYZE TABLE {table};"
            cursor.execute(sql)
            if table not in ['T_ship_pvp_leaderboard', 'STAGING_ship_recent_data']:
                sql = f"SELECT MAX(id) FROM {table};"
                cursor.execute(sql)
                data = cursor.fetchone()
                total_rows += data[0] if data[0] else 0
            pbar.update()

    sql = """
        SELECT 
            SUM(data_length + index_length)
        FROM information_schema.tables
        WHERE table_schema = DATABASE();
    """
    cursor.execute(sql)
    data = cursor.fetchone()
    if not data:
        total_size_kb = 0
    else:
        total_size_kb = data[0] // 1024

    logger.info(
        f"Tables: {table_count}  "
        f"Rows: {total_rows}  "
        f"Size: {total_size_kb} KB"
    )
    return table_count, total_rows, total_size_kb

def refresh_database_meta(cursor, key: str, value: int) -> None:
    """更新 leaderboard_rows 的统计数据"""
    sql = """
        UPDATE T_database_meta 
        SET 
            metric_value = %s 
        WHERE metric_key = %s;
    """
    cursor.execute(sql, [value, key])

def main():
    conn = pymysql.connect(**DB_CONFIG)
    sqlite_files, sqlite_sizes = analyze_sqlite_files()
    try:
        with conn.cursor() as cursor:
            mysql_tables,mysql_rows,mysql_sizes = anaylyze_mysql_tables(cursor)
            refresh_database_meta(cursor, 'mysql_tables', mysql_tables)
            refresh_database_meta(cursor, 'mysql_rows', mysql_rows)
            refresh_database_meta(cursor, 'mysql_size_kb', mysql_sizes)
            refresh_database_meta(cursor, 'sqlite_files', sqlite_files)
            refresh_database_meta(cursor, 'sqlite_size_kb', sqlite_sizes)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """数据库分析脚本

    该脚本不会影响其他子服务的正常运行

    使用示例：
    python scripts/maintenance/analyze.py
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)