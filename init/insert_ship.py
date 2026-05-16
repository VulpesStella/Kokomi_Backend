import os
import csv
import json
import logging
import pymysql
from tqdm import tqdm
from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

if (ROOT_DIR / 'env.dev').exists():
    logger.info('Loading environment file: env.dev')
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    logger.info('Loading environment file: env.pros')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DATA_DIR = Path(os.getenv("DATA_DIR"))

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

file_path = DATA_DIR / 'const/constants.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    SHIP_INIT_TABLE_LIST: list = data['SHIP_INIT_TABLE_LIST']

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
METRIC_IDS = [3, 5, 7, 8, 9]

def parse_ship_row(row: dict) -> dict:
    """将 CSV 行解析为用于插入的船只参数字典"""
    ship_id = int(row['ship_id'])
    return {
        'ship_id': ship_id,
        'is_old': bool(int(row.get('is_old', 0))),
        'tier': int(row['tier']),
        'type_id': TYPE_MAP.get(row['type'], 1),
        'nation_id': NATION_MAP.get(row['nation'], 1),
        'rarity_id': RARITY_MAP.get(row.get('rarity', '')),
        'premium': bool(int(row.get('premium', 0))),
        'special': bool(int(row.get('special', 0))),
        'index_code': row.get('index', ''),
        'zh_cn': row.get('zh_cn', ''),
        'zh_sg': row.get('zh_sg', ''),
        'zh_tw': row.get('zh_tw', ''),
        'en_short': row.get('en_short', ''),
        'en_full': row.get('en_full', ''),
        'ja': row.get('ja', ''),
        'ru': row.get('ru', ''),
        'verify': bool(int(row.get('verify', 0))),
    }

def insert_ship(cursor, ship: dict) -> None:
    """插入一条船只数据"""
    # 基础表
    sql = """
        INSERT INTO T_ship_base (
            ship_id, is_enabled, is_old, tier, type_id,
            nation_id, rarity_id, premium, special, index_code
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    cursor.execute(sql, [
        ship['ship_id'], True, ship['is_old'], ship['tier'], ship['type_id'],
        ship['nation_id'], ship['rarity_id'], ship['premium'], ship['special'],
        ship['index_code']
    ])

    # 名称表
    sql = """
        INSERT INTO T_ship_name (
            ship_id, zh_cn, zh_sg, zh_tw, en_short, en_full, ja, ru, verify
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    cursor.execute(sql, [
        ship['ship_id'], ship['zh_cn'], ship['zh_sg'], ship['zh_tw'],
        ship['en_short'], ship['en_full'], ship['ja'], ship['ru'], ship['verify']
    ])

    # 统计表
    for table_name in SHIP_INIT_TABLE_LIST:
        sql = f"""
            INSERT INTO {table_name} (ship_id) VALUES (%s);
        """
        cursor.execute(sql, [ship['ship_id']])

    # PvP 极值记录
    for metric_id in METRIC_IDS:
        sql = """
            INSERT INTO T_ship_pvp_record
            (ship_id, metric_id)
            VALUES (%s, %s);
        """
        cursor.execute(sql, [ship['ship_id'], metric_id])

def main(filepath: Path):
    """从CSV文件初始化所有船只相关表"""
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            ships = list(reader)
        logger.info(f'Found {len(ships)} ships in CSV')
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return
    
    if not ships:
        print('No ships to process, exiting')
        return
    
    # 数据库操作
    conn = pymysql.connect(**DB_CONFIG)
    try:
        conn.begin()
        with conn.cursor() as cursor:
            with tqdm(ships, desc="Inserting clans", total=len(ships)) as pbar:
                for item in pbar:
                    ship_id = int(item['ship_id'])
                    pbar.set_postfix_str(str(ship_id))
                    ship = parse_ship_row(item)
                    insert_ship(cursor, ship)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    
    logger.info("Initialization completed")


if __name__ == '__main__':
    """船只数据初始化工具。
    
    从CSV文件读取船只数据，初始化所有相关表。
    
    使用示例：
    python init/insert_ship.py
    """
    filepath = ROOT_DIR / 'init/data/ship_name_wg.csv'

    try:
        main(filepath)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)