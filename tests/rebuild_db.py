import os
import pymysql
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

if __name__ == '__main__':
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()
    cursor = conn.cursor()
    ROOT_DIR = Path(__file__).resolve().parent.parent
    cursor.execute(f"DROP DATABASE IF EXISTS `{DATABASE}`;")
    cursor.execute(f"CREATE DATABASE `{DATABASE}`;")
    cursor.execute(f"USE `{DATABASE}`;")
    sql_file = ROOT_DIR / "init/mysql/01-schema.sql"
    with conn.cursor() as cursor:
        with sql_file.open("r", encoding="utf-8") as f:
            sql = f.read()
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
    conn.commit()
    conn.close()
    print('Success')