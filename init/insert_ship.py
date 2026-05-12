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
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

ROOT_DIR = Path(__file__).resolve().parent.parent

# 类型映射（来自 D_ship_type）
TYPE_MAP = {
    'AirCarrier': 1,
    'Battleship': 2,
    'Cruiser': 3,
    'Destroyer': 4,
    'Submarine': 5
}

# 国家映射（来自 D_ship_nation）
NATION_MAP = {
    'usa': 1,
    'japan': 2,
    'germany': 3,
    'uk': 4,
    'ussr': 5,
    'france': 6,
    'italy': 7,
    'pan_asia': 8,
    'europe': 9,
    'netherlands': 10,
    'commonwealth': 11,
    'pan_america': 12,
    'spain': 13
}

# 稀有度映射（来自 D_ship_rarity）
RARITY_MAP = {
    '': None,
    'Common': 1,
    'Uncommon': 2,
    'Rare': 3,
    'Epic': 4,
    'Legendary': 5
}

# 需要初始化的 PvP 极值记录指标 ID
METRIC_IDS = [3, 4, 5, 7, 8, 9]


def init_ship_data():
    """从CSV文件初始化所有船只相关表"""
    CSV_FILE_PATH = ROOT_DIR / 'init/data/ship_name_wg.csv'
    
    try:
        with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            ships_data = list(reader)
        print(f'Found {len(ships_data)} ships')
    except FileNotFoundError:
        print(f'Error: CSV file not found at {CSV_FILE_PATH}')
        return
    except Exception as e:
        print(f'Error reading CSV file: {e}')
        return
    
    if not ships_data:
        print('No ships to insert. Exiting.')
        return
    
    # 数据库操作
    conn = pymysql.connect(**DB_CONFIG)
    conn.begin()
    try:
        with conn.cursor() as cursor:
            for ship in ships_data:
                ship_id = int(ship['ship_id'])
                is_old = bool(int(ship.get('is_old', 0)))
                tier = int(ship['tier'])
                type_id = TYPE_MAP.get(ship['type'], 1)
                nation_id = NATION_MAP.get(ship['nation'].lower(), 1)
                rarity_id = RARITY_MAP.get(ship.get('rarity', '').strip())
                premium = bool(int(ship.get('premium', 0)))
                special = bool(int(ship.get('special', 0)))
                index_code = ship.get('index', '')
                
                # 1. 插入 T_ship_base
                cursor.execute("""
                    INSERT INTO T_ship_base (
                        ship_id, is_enabled, is_old, tier, type_id, 
                        nation_id, rarity_id, premium, special, index_code
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    ship_id, True, is_old, tier, type_id,
                    nation_id, rarity_id, premium, special, index_code
                ))
                
                # 2. 插入 T_ship_name
                cursor.execute("""
                    INSERT INTO T_ship_name (
                        ship_id, zh_cn, zh_sg, zh_tw, en_short, en_full, ja, ru, verify
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    ship_id,
                    ship.get('zh_cn', ''),
                    ship.get('zh_sg', ''),
                    ship.get('zh_tw', ''),
                    ship.get('en_short', ''),
                    ship.get('en_full', ''),
                    ship.get('ja', ''),
                    ship.get('ru', ''),
                    bool(int(ship.get('verify', 0)))
                ))
                
                # 3. 插入 T_ship_pvp_stats
                cursor.execute("""
                    INSERT INTO T_ship_pvp_stats (ship_id)
                    VALUES (%s)
                """, (ship_id,))
                
                # 4. 插入 T_ship_stats_by_battles
                cursor.execute("""
                    INSERT INTO T_ship_stats_by_battles (ship_id)
                    VALUES (%s)
                """, (ship_id,))
                
                # 5. 插入 T_ship_stats_by_users
                cursor.execute("""
                    INSERT INTO T_ship_stats_by_users (ship_id)
                    VALUES (%s)
                """, (ship_id,))
                
                # 6. 插入 T_ship_rating_distribution
                cursor.execute("""
                    INSERT INTO T_ship_rating_distribution 
                    (ship_id, top1, top5, top10, top15, top50, top75, top90)
                    VALUES (%s, 0, 0, 0, 0, 0, 0, 0)
                """, (ship_id,))
                
                # 7. 插入 T_ship_pvp_record（每个ship 6条记录）
                for metric_id in METRIC_IDS:
                    cursor.execute("""
                        INSERT INTO T_ship_pvp_record 
                        (ship_id, metric_id, metric_value, users_count)
                        VALUES (%s, %s, 0, 0)
                    """, (ship_id, metric_id))
        
        conn.commit()
        print(f'Success: Initialized {len(ships_data)} ships!')
        
    except Exception as e:
        conn.rollback()
        print(f'Error: Initialization failed - {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """船只数据初始化工具。
    
    从CSV文件读取船只数据，初始化所有相关表。
    
    使用示例：
    python init/insert_ship.py
    """
    init_ship_data()