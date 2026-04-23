import os
import pymysql
from pymysql.constants import CLIENT
from pathlib import Path
from dotenv import load_dotenv


load_dotenv('env.dev')
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    'autocommit': False
}
DATABASE = os.getenv("MYSQL_DATABASE")
ROOT_DIR = Path(__file__).resolve().parent.parent

def rebuild_db():
    conn = pymysql.connect(
        **DB_CONFIG,
        client_flag=CLIENT.MULTI_STATEMENTS
    )
    cursor = conn.cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS `{DATABASE}`;")
    cursor.execute(f"CREATE DATABASE `{DATABASE}`;")
    cursor.execute(f"USE `{DATABASE}`;")
    sql_files = [
        ROOT_DIR / "init/mysql/01-schemas.sql",
        ROOT_DIR / "init/mysql/02-functions.sql",
        ROOT_DIR / "init/mysql/03-views.sql",
        ROOT_DIR / "init/mysql/04-datas.sql"
    ]
    for sql_file in sql_files:
        with sql_file.open("r", encoding="utf-8") as f:
            sql = f.read()
            cursor.execute(sql)
    conn.commit()
    conn.close()
    print(f'Success: {DATABASE}')

if __name__ == '__main__':
    """用于在本地开发环境中，删除并重建数据库。

    注意：严禁在开发环境下使用！！！

    使用示例：
    python tests/rebuild_db.py
    """
    # 仅允许在 Windows 环境执行
    if os.name != 'nt':
        print("❌ This script can only be run on Windows environment.")
        exit(1)
    rebuild_db()