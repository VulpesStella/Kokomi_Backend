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
        ROOT_DIR / "init/mysql/01-schemas/01-base.sql",
        ROOT_DIR / "init/mysql/01-schemas/02-user.sql",
        ROOT_DIR / "init/mysql/01-schemas/03-clan.sql",
        ROOT_DIR / "init/mysql/01-schemas/04-ship.sql",
        ROOT_DIR / "init/mysql/01-schemas/05-recent.sql",
        ROOT_DIR / "init/mysql/02-data/01-base.sql",
        ROOT_DIR / "init/mysql/03-views/01-base.sql",
        ROOT_DIR / "init/mysql/04-functions/01-base.sql"
    ]
    for sql_file in sql_files:
        print(f'Executing...   {sql_file}')
        with sql_file.open("r", encoding="utf-8") as f:
            sql = f.read()
            cursor.execute(sql)
    conn.commit()
    conn.close()
    print(f'Success: {DATABASE}')

if __name__ == '__main__':
    """用于在数据库初始化，删除并重建数据库

    使用示例：
    python init/rebuild_db.py
    """
    rebuild_db()