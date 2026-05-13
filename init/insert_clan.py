import os
import csv
import pymysql
from pathlib import Path
from dotenv import load_dotenv


load_dotenv('env.prod')
DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

ROOT_DIR = Path(__file__).resolve().parent.parent


def init_clan_data():
    """从CSV文件初始化公会相关表
    
    流程：
    1. 读取CSV文件中 members_count > 0 的公会数据
    2. 向 T_clan_base 插入 clan_id, tag, updated_at
    3. 向 T_clan_users 和 T_clan_stats 插入 clan_id
    """
    # 读取CSV数据
    clans_to_insert = []
    CSV_FILE_PATH = ROOT_DIR / 'temp/clan_data.csv'
    try:
        with open(CSV_FILE_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                members_count = int(row['members_count'])
                if members_count > 0:
                    clans_to_insert.append({
                        'clan_id': int(row['clan_id']),
                        'tag': row['tag']
                    })
        print(f'Found {len(clans_to_insert)} clans with members > 0')
    except FileNotFoundError:
        print(f'Error: CSV file not found at {CSV_FILE_PATH}')
        return
    except Exception as e:
        print(f'Error reading CSV file: {e}')
        return
    
    if not clans_to_insert:
        print('No clans to insert. Exiting.')
        return
    
    # 数据库操作
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()
    try:
        with conn.cursor() as cursor:
            for clan in clans_to_insert:
                # 步骤2：插入 T_clan_base 表
                sql = """
                    INSERT INTO T_clan_base (
                        clan_id, 
                        tag,  
                        table_count, 
                        updated_at 
                    ) VALUES (
                        %s, %s, 2, NOW()
                    )
                """
                cursor.execute(sql, (clan['clan_id'], clan['tag']))
            
                sql = """
                    INSERT INTO T_clan_users (clan_id)
                    VALUES (%s)
                """
                cursor.execute(sql, (clan['clan_id'],))
            
                sql = """
                    INSERT INTO T_clan_stats (clan_id)
                    VALUES (%s)
                """
                cursor.execute(sql, (clan['clan_id'],))

                sql = """
                    UPDATE T_clan_base 
                    SET 
                        table_count = 2 
                    WHERE clan_id = %s;
                """
                cursor.execute(sql, (clan['clan_id'],))
        
        conn.commit()
        print(f'\nSuccess: Initialized {len(clans_to_insert)} clans!')
        
    except Exception as e:
        conn.rollback()
        print(f'\nError: Initialization failed - {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """公会数据初始化工具。
    
    从CSV文件读取 members_count > 0 的公会数据，
    初始化 T_clan_base、T_clan_users、T_clan_stats 三个表。
    
    使用示例：
    python init/insert_clan.py
    """
    
    init_clan_data()