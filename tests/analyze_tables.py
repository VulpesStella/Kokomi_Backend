import os
import pymysql
from dotenv import load_dotenv

load_dotenv('env.dev')

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}


def analyze_all_tables():
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()

    try:
        with conn.cursor() as cursor:
            # 获取当前库所有表
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE();
            """)

            tables = [row[0] for row in cursor.fetchall()]

            print(f"Total tables: {len(tables)}")

            for table in tables:
                try:
                    sql = f"ANALYZE TABLE {table};"
                    cursor.execute(sql)
                    print(f"Analyzed: {table}")
                except Exception as e:
                    print("Error:", e)

        conn.commit()
        print("Success")

    except Exception as e:
        conn.rollback()
        print("Error:", e)

    finally:
        conn.close()


if __name__ == '__main__':
    """
    对当前数据库所有表执行 ANALYZE TABLE

    用途：
    - 刷新 InnoDB 统计信息
    - 优化查询计划

    使用：
    python tests/analyze_tables.py
    """

    # 仅允许在 Windows 环境执行
    if os.name != 'nt':
        print("❌ This script can only be run on Windows environment.")
        exit(1)

    analyze_all_tables()