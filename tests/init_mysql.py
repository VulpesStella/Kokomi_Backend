#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pymysql
import traceback
from pathlib import Path
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env.prod')
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "autocommit": False
}

def exec_sql_file(cursor, file_path: Path):
    print(f"Executing {file_path.name}")
    with file_path.open("r", encoding="utf-8") as f:
        sql = f.read()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(stmt)
                raise e

def main():
    sql_files = [
        ROOT_DIR / "init/mysql/01-schema.sql",
        ROOT_DIR / "init/mysql/02-data.sql",
    ]
    for f in sql_files:
        if not f.exists():
            print(f"Missing SQL file: {f}")
            return
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cursor:
            for sql_file in sql_files:
                exec_sql_file(cursor, sql_file)
        print("MySQL initialization finished")
        conn.commit()
    except:
        conn.rollback()
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
