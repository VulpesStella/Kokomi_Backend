import os
import csv
import json
import gzip
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
    'charset': 'utf8mb4'
}

# 备份目录
BACKUP_DIR = ROOT_DIR / 'data/trash'

# 批次大小
BATCH_SIZE = 50000

file_path = ROOT_DIR / 'data/json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']


def get_max_id(cursor, table_name: str) -> int:
    """获取表中最大的ID值"""
    cursor.execute(f"SELECT MAX(id) FROM {table_name};")
    result = cursor.fetchone()
    max_id = result[0] if result[0] else 0
    logger.info(f"Table {table_name} max id: {max_id:,}")
    return max_id


def export_table_to_compressed_csv(
    cursor, 
    table_name: str, 
    export_columns: list, 
    output_file: Path
):
    """
    导出表数据到压缩CSV文件
    
    Args:
        cursor: 数据库游标
        table_name: 表名
        id_column: ID列名（用于分批）
        export_columns: 要导出的列名列表
        output_file: 输出文件路径
    """
    # 构建SQL
    columns_str = ', '.join(export_columns)
    sql = f"""
        SELECT {columns_str} 
        FROM {table_name} 
        WHERE id BETWEEN %s AND %s;
    """
    
    max_id = get_max_id(cursor, table_name)
    if max_id == 0:
        logger.warning(f"No data found in table {table_name}")
        return
    
    total_rows = 0
    batch_count = 0
    
    # 使用gzip压缩写入CSV
    with gzip.open(output_file, 'wt', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        
        # 写入表头
        writer.writerow(export_columns)
        total_rows += 1  # 计入表头
        
        # 分批查询和写入（使用BETWEEN）
        for start_id in range(1, max_id + 1, BATCH_SIZE):
            end_id = min(start_id + BATCH_SIZE - 1, max_id)  # BETWEEN是闭区间，需要减1
            batch_count += 1
            
            cursor.execute(sql, (start_id, end_id))
            
            batch_rows = 0
            while True:
                rows = cursor.fetchmany(10000)
                if not rows:
                    break
                
                # 批量写入CSV
                writer.writerows(rows)
                batch_rows += len(rows)
            
            total_rows += batch_rows
    
    # 获取压缩后大小
    compressed_size = output_file.stat().st_size / 1024 / 1024
    logger.info(f"  Exported {total_rows - 1:,} rows from {table_name}")
    logger.info(f"  Compressed size: {compressed_size:.2f} MB")


def backup_users(cursor):
    """备份用户数据表 T_user_base"""
    logger.info("=" * 60)
    logger.info("Backing up user data...")
    
    output_file = BACKUP_DIR / f"backup_users_{REGION}.csv.gz"
    
    return export_table_to_compressed_csv(
        cursor=cursor,
        table_name='T_user_base',
        export_columns=['account_id', 'username'],
        output_file=output_file
    )


def backup_clans(cursor):
    """备份工会数据表 T_clan_base"""
    logger.info("=" * 60)
    logger.info("Backing up clan data...")
    
    output_file = BACKUP_DIR / f"backup_clans_{REGION}.csv.gz"
    
    return export_table_to_compressed_csv(
        cursor=cursor,
        table_name='T_clan_base',
        export_columns=['clan_id', 'tag'],
        output_file=output_file
    )


def main():
    """主函数：备份用户和工会数据"""
    conn = None
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 备份用户数据
        backup_users(cursor)
        
        # 备份工会数据
        backup_clans(cursor)
        
    except Exception as e:
        logger.exception(f"Backup failed: {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")


if __name__ == '__main__':
    """数据库备份工具 - 自动备份用户和工会数据
    
    使用方法：
        python tools/backup.py
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Backup interrupted by user")