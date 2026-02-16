import pymysql
from datetime import datetime, timedelta

# ===== 数据库配置 =====
DB_CONFIG = {
    "host": "129.226.90.10",
    "port": 3306,
    "user": "root",
    "password": "qazwsxedc0258@",
    "database": "kokomi"
}

def main():
    # 计算时间
    one_year_ago = datetime.now() - timedelta(days=365)

    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT COUNT(*)
                FROM user_info
                WHERE last_battle_at < %s
            """
            cursor.execute(sql, (one_year_ago,))
            result = cursor.fetchone()

            count = result[0]
            print(f"1年以上未战斗的用户数量: {count}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
