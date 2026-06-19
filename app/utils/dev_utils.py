import csv

from app.core import EnvConfig

SHIP_TYPE_MAP = {
    1: 'AirCarrier',
    2: 'Battleship',
    3: 'Cruiser',
    4: 'Destroyer',
    5: 'Submarine'
}
SHIP_NATION_MAP = {
    1: 'usa',
    2: 'japan',
    3: 'germany',
    4: 'uk',
    5: 'ussr',
    6: 'france',
    7: 'italy',
    8: 'pan_asia',
    9: 'europe',
    10: 'netherlands',
    11: 'commonwealth',
    12: 'pan_america',
    13: 'spain'
}

class DevUtils:
    def read_ship_stats() -> dict:
        """读取本地船只服务数据"""
        file_path = EnvConfig.INIT_DIR / f"data/ship_stats.csv"
        if not file_path.exists():
            return {}
        
        result = {}
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)  # 列名: ship_id, win_rate, avg_damage, avg_frags
            for row in reader:
                ship_id = str(row['ship_id'])
                win_rate = float(row['win_rate'])
                avg_damage = float(row['avg_damage'])
                avg_frags = float(row['avg_frags'])
                result[ship_id] = [win_rate, avg_damage, avg_frags]
        return result
    
    def read_ship_info() -> dict:
        """读取船只信息 CSV 文件"""
        if EnvConfig.REGION == 'ru':
            file_path = EnvConfig.INIT_DIR / f"data/ship_name_lesta.csv"
        else:
            file_path = EnvConfig.INIT_DIR / f"data/ship_name_wg.csv"

        if not file_path.exists():
            return {}
        
        result = {}
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ship_id = str(row['ship_id'])
                is_old = int(row['is_old'])
                tier = int(row['tier'])
                type_id = row['type_id']
                nation_id = row['nation_id']
                result[ship_id] = [is_old, tier, SHIP_TYPE_MAP.get(type_id), SHIP_NATION_MAP.get(nation_id)]
        return result