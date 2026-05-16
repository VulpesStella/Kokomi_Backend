import os
import json
import traceback
from pathlib import Path

import pymysql
from dotenv import load_dotenv


ROOT_DIR = Path(os.getcwd())

if (ROOT_DIR / 'env.dev').exists():
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('Dead env file failed')

DATA_DIR = Path(os.getenv("DATA_DIR"))

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}

constants_path = DATA_DIR / 'const' / 'constants.json'
with open(constants_path, "r", encoding="utf-8") as f:
    data = json.load(f)
USER_INIT_TABLE_LIST = data['USER_INIT_TABLE_LIST']
CLAN_INIT_TABLE_LIST = data['CLAN_INIT_TABLE_LIST']

# ----------------------------------------------------------------------
# 辅助函数（含统计输出）
# ----------------------------------------------------------------------

def _verify_database(cursor, index: str, table_names: list) -> int:
    """校验 user 或 clan 基础表与关联子表的数据完整性"""
    fixed_count = 0
    id_str = 'account_id' if index == 'user' else 'clan_id'

    # 找出 table_count 不满足应有数量的记录
    sql = f"""
        SELECT 
            {id_str}
        FROM T_{index}_base
        WHERE table_count < %s;
    """
    cursor.execute(sql, [len(table_names)])
    broken_ids = [row[0] for row in cursor.fetchall()]
    broken_count = len(broken_ids)

    if broken_count == 0:
        print(f"[{index.upper()}] 未发现不完整记录（应有 {len(table_names)} 个子表）。")
        return 0

    print(f"[{index.upper()}] 发现 {broken_count} 条缺失子表的记录（共需 {len(table_names)} 个子表），开始修复…")

    for entity_id in broken_ids:
        for table_name in table_names:
            sql = f"""
                SELECT {id_str}
                FROM {table_name}
                WHERE {id_str} = %s;
            """
            cursor.execute(sql, [entity_id])
            result = cursor.fetchone()
            if result is None:
                sql = f"""
                    INSERT INTO {table_name} ({id_str})
                    VALUES (%s);
                """
                cursor.execute(sql, [entity_id])
                sql = f"""
                    UPDATE T_{index}_base
                    SET table_count = table_count + 1
                    WHERE {id_str} = %s;
                """
                cursor.execute(sql, [entity_id])
                fixed_count += 1

    print(f"[{index.upper()}] 修复完成，共补充 {fixed_count} 行缺失数据。")
    return fixed_count


def _verify_ship_archive(cursor) -> int:
    """确保近期数据存档表包含最新版本下所有船只的记录"""
    # 获取最新版本号
    cursor.execute("""
        SELECT 
            short_name
        FROM T_game_version
        WHERE is_latest = TRUE;
    """)
    result = cursor.fetchone()
    if not result:
        print("[SHIP_ARCHIVE] 未找到最新版本，跳过。")
        return 0
    version = result[0]

    # 获取全部 ship_id
    cursor.execute("SELECT ship_id FROM T_ship_base;")
    ship_ids = [row[0] for row in cursor.fetchall()]
    total_ships = len(ship_ids)
    if total_ships == 0:
        print("[SHIP_ARCHIVE] T_ship_base 无数据，跳过。")
        return 0

    # 已归档的 ship_id
    cursor.execute("""
        SELECT 
            ship_id
        FROM ARCH_ship_stats_by_recent
        WHERE game_version = %s;
    """, [version])
    archived_ids = {row[0] for row in cursor.fetchall()}
    archived_count = len(archived_ids)
    missing_ids = [sid for sid in ship_ids if sid not in archived_ids]
    missing_count = len(missing_ids)

    if missing_count == 0:
        print(f"[SHIP_ARCHIVE] 版本 '{version}'：共 {total_ships} 艘船，已全部归档。")
        return 0

    print(f"[SHIP_ARCHIVE] 版本 '{version}'：共 {total_ships} 艘船，已归档 {archived_count} 艘，缺失 {missing_count} 艘，开始补全…")

    for ship_id in missing_ids:
        cursor.execute("""
            INSERT INTO ARCH_ship_stats_by_recent 
                (ship_id, game_version)
            VALUES 
                (%s, %s);
        """, [ship_id, version])

    print(f"[SHIP_ARCHIVE] 已插入 {missing_count} 条缺失归档记录。")
    return missing_count


def maintenance_database(cursor) -> None:
    """修复用户和公会基础表中缺失的关联数据行，并补全近期数据存档"""
    print("开始数据库维护检测…")
    fixed_total = 0
    fixed_total += _verify_database(cursor, 'user', USER_INIT_TABLE_LIST)
    fixed_total += _verify_database(cursor, 'clan', CLAN_INIT_TABLE_LIST)
    fixed_total += _verify_ship_archive(cursor)

    if fixed_total > 0:
        print(f"\n>>> 维护完成，总计修复 {fixed_total} 行数据。")
    else:
        print("\n>>> 维护完成，未发现任何异常。")


def maintenance_table():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            maintenance_database(cursor)
        conn.commit()
    except Exception:
        conn.rollback()
        print("Error during maintenance:")
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    # python tools/maintenance.py
    maintenance_table()