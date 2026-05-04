import os
import argparse
import pymysql
from pathlib import Path
from dotenv import load_dotenv


load_dotenv('env.dev')
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}


def init_ship_rating_distribution():
    """初始化 T_ship_rating_distribution 表
    
    流程：
    1. 从 T_ship_base 获取所有 ship_id
    2. 为每个 ship_id 初始化空记录（所有 top 字段为 0）
    """
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()
    try:
        with conn.cursor() as cursor:
            # 步骤1：获取所有 ship_id
            print('Step 1: Fetching all ship_id from T_ship_base...')
            cursor.execute("SELECT ship_id FROM T_ship_base")
            ship_ids = [row[0] for row in cursor.fetchall()]
            print(f'  -> Found {len(ship_ids)} ships')

            # 步骤2：清空并初始化
            print('Step 2: Clearing and initializing T_ship_rating_distribution...')
            cursor.execute("TRUNCATE TABLE T_ship_rating_distribution")
            
            insert_sql = """
                INSERT INTO T_ship_rating_distribution 
                (ship_id, sample_count, top1, top5, top10, top15, top50, top75, top90)
                VALUES (%s, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            """
            
            for ship_id in ship_ids:
                cursor.execute(insert_sql, (ship_id,))
            
            print(f'  -> Initialized {len(ship_ids)} empty records')

        conn.commit()
        print(f'\nSuccess: Initialization completed!')
        
        # 验证
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM T_ship_rating_distribution")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM T_ship_rating_distribution WHERE sample_count > 0")
            non_zero = cursor.fetchone()[0]
            print(f'\nVerification:')
            print(f'  -> Total records: {total}')
            print(f'  -> Non-zero records: {non_zero}')
            print(f'  -> Zero records: {total - non_zero}')
            
    except Exception as e:
        conn.rollback()
        print(f'\nError: Initialization failed - {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    '''T_ship_rating_distribution 表初始化工具。
    
    为所有船只创建 Rating 分布空记录，后续由统计程序更新实际数据。
    
    使用示例：
    python tests/insert_data.py
    '''
    parser = argparse.ArgumentParser(description='Initialize T_ship_rating_distribution table')
    args = parser.parse_args()
    init_ship_rating_distribution()