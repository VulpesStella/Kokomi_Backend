import os
import csv
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
ROOT_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = ROOT_DIR / 'init/data/ship_name_wg.csv'

TYPE_MAP = {
    "AirCarrier": 1,
    "Battleship": 2,
    "Cruiser": 3,
    "Destroyer": 4,
    "Submarine": 5
}
NATION_MAP = {
    "usa": 1,
    "japan": 2,
    "germany": 3,
    "uk": 4,
    "ussr": 5,
    "france": 6,
    "italy": 7,
    "pan_asia": 8,
    "europe": 9,
    "netherlands": 10,
    "commonwealth": 11,
    "pan_america": 12,
    "spain": 13
}
RARITY_MAP = {
    "Common": 1,
    "Uncommon": 2,
    "Rare": 3,
    "Epic": 4,
    "Legendary": 5
}

def insert_ships_from_csv():
    conn = pymysql.connect(**DB_CONFIG, database=DATABASE)
    cursor = conn.cursor()
    with CSV_FILE.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ship_id = int(row["ship_id"])
            tier = int(row["tier"])
            type_id = TYPE_MAP.get(row["type"], 1)
            nation_id = NATION_MAP.get(row["nation"].lower(), 1)
            is_old = bool(int(row['is_old']))
            premium = bool(int(row["premium"]))
            special = bool(int(row["special"]))
            verify = bool(int(row["verify"]))

            rarity_id = RARITY_MAP.get(row["rarity"], None)
            index_code = row.get("index") or None
            name_en_short = row.get("en_short") or None
            name_en_full = row.get("en_full") or None
            name_zh_cn = row.get("zh_cn") or None
            name_zh_sg = row.get("zh_sg") or None
            name_zh_tw = row.get("zh_tw") or None
            name_ja = row.get("ja") or None
            name_ru = row.get("ru") or None

            sql = """
                INSERT INTO T_ship_base (
                    ship_id, 
                    is_enabled,
                    is_old,
                    tier, 
                    type_id, 
                    nation_id, 
                    rarity_id, 
                    premium, 
                    special, 
                    index_code
                )VALUES (
                    %s, 1, %s, %s, %s, %s, %s, %s, %s, %s
                );
            """
            cursor.execute(sql, (
                ship_id, is_old, tier, type_id, nation_id, rarity_id, premium, special, index_code
            ))
            sql = """
                INSERT INTO T_ship_name (
                    ship_id, 
                    zh_cn, 
                    zh_sg, 
                    zh_tw, 
                    en_short, 
                    en_full, 
                    ja, 
                    ru, 
                    verify
                )VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
            """
            cursor.execute(sql, (
                ship_id, name_zh_cn, name_zh_sg, name_zh_tw, name_en_short, name_en_full, name_ja, name_ru, verify
            ))
            sql = """
                INSERT INTO T_ship_stats_by_battles (
                    ship_id
                )VALUES (
                    %s
                );
            """
            cursor.execute(sql, (
                ship_id
            ))
            sql = """
                INSERT INTO T_ship_stats_by_users (
                    ship_id
                )VALUES (
                    %s
                );
            """
            cursor.execute(sql, (
                ship_id
            ))
    conn.commit()
    conn.close()
    print("All ship data inserted successfully.")

if __name__ == '__main__':
    # 仅允许在 Windows 环境执行
    if os.name != 'nt':
        print("❌ This script can only be run on Windows environment.")
        exit(1)
    insert_ships_from_csv()