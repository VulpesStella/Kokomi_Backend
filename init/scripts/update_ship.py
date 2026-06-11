import os
import csv
import json
import logging
import pymysql
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

# 加载环境变量
if (ROOT_DIR / 'env.dev').exists():
    logger.info('Loading environment file: env.dev')
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    logger.info('Loading environment file: env.prod')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

# 读取区域配置
file_path = ROOT_DIR / 'data/json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']

# 读取常量配置
file_path = ROOT_DIR / 'data/const/constants.json'
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
METRIC_IDS = [3, 4, 5, 7, 8, 9]


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


def main(filepath: Path):
    """从CSV文件增量更新船只相关表（对比数据库与CSV，执行INSERT/DISABLE/UPDATE）"""
    if not filepath.exists():
        logger.error(f"CSV file not found: {filepath}")
        return

    # 读取并解析CSV
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            raw_ships = list(reader)
        logger.info(f'Found {len(raw_ships)} ships in CSV')
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return

    if not raw_ships:
        logger.warning('No ships to process, exiting')
        return

    ships = [parse_ship_row(row) for row in raw_ships]
    csv_ship_map: dict[int, dict] = {s['ship_id']: s for s in ships}
    csv_ship_ids: set[int] = set(csv_ship_map.keys())

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ship_id, is_enabled FROM T_ship_base")
            db_rows = cursor.fetchall()
        db_ship_map: dict[int, bool] = {row[0]: bool(row[1]) for row in db_rows}
        db_ship_ids: set[int] = set(db_ship_map.keys())

        new_ship_ids = csv_ship_ids - db_ship_ids
        disable_ship_ids = {sid for sid, enabled in db_ship_map.items()
                            if enabled and sid not in csv_ship_ids}
        update_ship_ids = csv_ship_ids & db_ship_ids

        with conn.cursor() as cursor:
            if new_ship_ids:
                base_data = []
                for sid in new_ship_ids:
                    s = csv_ship_map[sid]
                    prefix, name = s['index_code'].split('_', 1)
                    base_data.append((
                        s['ship_id'], True, s['is_old'], s['tier'],
                        s['type_id'], s['nation_id'], s['rarity_id'],
                        s['premium'], s['special'], prefix, name
                    ))
                sql_base = """
                    INSERT INTO T_ship_base (
                        ship_id, is_enabled, is_old, tier, type_id,
                        nation_id, rarity_id, premium, special, index_code, ship_name
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(sql_base, base_data)

                name_data = []
                for sid in new_ship_ids:
                    s = csv_ship_map[sid]
                    name_data.append((
                        s['ship_id'], s['zh_cn'], s['zh_sg'], s['zh_tw'],
                        s['en_short'], s['en_full'], s['ja'], s['ru'], s['verify']
                    ))
                sql_name = """
                    INSERT INTO T_ship_name (
                        ship_id, zh_cn, zh_sg, zh_tw, en_short, en_full, ja, ru, verify
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(sql_name, name_data)

                for table_name in SHIP_INIT_TABLE_LIST:
                    sql_init = f"INSERT INTO {table_name} (ship_id) VALUES (%s)"
                    cursor.executemany(sql_init, [(sid,) for sid in new_ship_ids])

                pvp_data = []
                for sid in new_ship_ids:
                    for metric_id in METRIC_IDS:
                        pvp_data.append((sid, metric_id))
                sql_pvp = """
                    INSERT INTO T_ship_pvp_record (ship_id, metric_id) VALUES (%s, %s)
                """
                cursor.executemany(sql_pvp, pvp_data)

            if disable_ship_ids:
                sql_disable = "UPDATE T_ship_base SET is_enabled = 0 WHERE ship_id = %s"
                cursor.executemany(sql_disable, [(sid,) for sid in disable_ship_ids])

            if update_ship_ids:
                base_update_data = []
                for sid in update_ship_ids:
                    s = csv_ship_map[sid]
                    base_update_data.append((
                        s['is_old'], s['rarity_id'], s['premium'], s['special'],
                        s['ship_id']
                    ))
                sql_base_update = """
                    UPDATE T_ship_base
                    SET is_old = %s, rarity_id = %s, premium = %s, special = %s
                    WHERE ship_id = %s
                """
                cursor.executemany(sql_base_update, base_update_data)

                name_update_data = []
                for sid in update_ship_ids:
                    s = csv_ship_map[sid]
                    name_update_data.append((
                        s['zh_cn'], s['zh_sg'], s['zh_tw'], s['en_short'],
                        s['en_full'], s['ja'], s['ru'], s['verify'],
                        s['ship_id']
                    ))
                sql_name_update = """
                    UPDATE T_ship_name
                    SET zh_cn = %s, zh_sg = %s, zh_tw = %s,
                        en_short = %s, en_full = %s, ja = %s, ru = %s, verify = %s
                    WHERE ship_id = %s
                """
                cursor.executemany(sql_name_update, name_update_data)

        conn.commit()

        logger.info(f"Inserted: {len(new_ship_ids)}, Updated: {len(update_ship_ids)}, "
                    f"Disabled: {len(disable_ship_ids)}")
    except Exception:
        conn.rollback()
        logger.exception("Operation failed, rolled back")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    """船只数据增量更新工具

    使用示例：
    python init/scripts/update_ship.py
    """
    if REGION == 'ru':
        filepath = ROOT_DIR / 'init/data/ship_name_lesta.csv'
    else:
        filepath = ROOT_DIR / 'init/data/ship_name_wg.csv'

    try:
        main(filepath)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")