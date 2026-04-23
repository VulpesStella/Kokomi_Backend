import os
import json
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
DATABASE = os.getenv("MYSQL_DATABASE")
ROOT_DIR = Path(__file__).resolve().parent.parent
file_path = ROOT_DIR / 'data/const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    USER_INIT_TABLE_LIST: list = data['USER_INIT_TABLE_LIST']
    CLAN_INIT_TABLE_LIST: list = data['CLAN_INIT_TABLE_LIST']

def insert_data(insert_type: str, insert_data: int):
    if insert_type == 'user':
        conn = pymysql.connect(**DB_CONFIG)
        conn.begin()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO T_user_base (
                    account_id, 
                    username
                ) VALUES (
                    %s, %s
                );
            """
            cursor.execute(sql, [insert_data, f'User_{insert_data}'])
            for table_name in USER_INIT_TABLE_LIST:
                sql = f"""
                    INSERT INTO {table_name} (
                        account_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [insert_data])
            sql = """
                UPDATE T_user_base 
                SET 
                    verify = 1 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [insert_data])
        conn.commit()
        conn.close()
    elif insert_type == 'clan':
        conn = pymysql.connect(**DB_CONFIG)
        conn.begin()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO T_clan_base (
                    clan_id, 
                    tag
                ) VALUES (
                    %s, %s
                );
            """
            cursor.execute(sql, [insert_data,'N/A'])
            for table_name in CLAN_INIT_TABLE_LIST:
                sql = f"""
                    INSERT INTO {table_name} (
                        clan_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [insert_data])
            sql = """
                UPDATE T_clan_base 
                SET 
                    verify = 1 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [insert_data])
        conn.commit()
        conn.close()
    else:
        raise ValueError(f"Unknown argument: {insert_type}")
    print(f'Success: {insert_type} -> {insert_data}')

if __name__ == '__main__':
    '''用于在本地开发环境中，向数据库中手动插入数据。
    

    参数说明：
    -t / --type  : 插入数据类型
    -i / --id    : 插入数据

    使用示例：
    python tests/insert_data.py -t clan -i 7000005269
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--type', required=True, help='Insert Type')
    parser.add_argument('-i', '--id', required=True, type=int, help='Insert Data')
    args = parser.parse_args()
    insert_data(args.type, args.id)