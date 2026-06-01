import os
import csv
import logging
import pymysql
import argparse
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
    logger.info('Loading environment file: env.prod')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DEV_MODE = os.getenv("DEV_MODE")

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    'autocommit': False
}

def read_ship_stats(ship_id: int):
    logger.info(f'Dev mode: {DEV_MODE}')
    if DEV_MODE == '1':
        file_path = ROOT_DIR / "init/data/ship_stats.csv"
        if not file_path.exists():
            return []
        
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['ship_id']) == ship_id:
                    win_rate = float(row['win_rate'])
                    avg_damage = float(row['avg_damage'])
                    avg_frags = float(row['avg_frags'])
                    return [win_rate, avg_damage, avg_frags]

        return []
    else:
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        win_rate, 
                        avg_damage, 
                        avg_frags 
                    FROM T_ship_stats_by_battles 
                    WHERE ship_id = %s;
                """
                cursor.execute(sql, [ship_id])
                data = cursor.fetchone()
                if data is None:
                    return []
                else:
                    return [data[0], data[1], data[2]]
        finally:
            conn.close()

def calc_ship_rating_python(ship_data: list, ship_stats: list):
    """计算PR值"""
    logger.info(f"ship_data: {ship_data}")
    logger.info(f"ship_stats: {ship_stats}")
    if ship_stats == []:
        return -1
    
    # Step 1 - ratios
    r_wins = ship_data[0] / ship_stats[0]
    r_dmg = ship_data[1] / ship_stats[1]
    r_frags = ship_data[2] / ship_stats[2]
    logger.info("")
    logger.info("Step 1 - Ratios:")
    logger.info(f"  r_wins = {ship_data[0]} / {ship_stats[0]} = {r_wins}")
    logger.info(f"  r_dmg = {ship_data[1]} / {ship_stats[1]} = {r_dmg}")
    logger.info(f"  r_frags = {ship_data[2]} / {ship_stats[2]} = {r_frags}")
    
    # Step 2 - normalization
    n_wins = max(0, (r_wins - 0.7) / (1 - 0.7))
    n_dmg = max(0, (r_dmg - 0.4) / (1 - 0.4))
    n_frags = max(0, (r_frags - 0.1) / (1 - 0.1))
    logger.info("")
    logger.info("Step 2 - Normalization:")
    logger.info(f"  n_wins = max(0, ({r_wins} - 0.7) / 0.3) = {n_wins}")
    logger.info(f"  n_dmg = max(0, ({r_dmg} - 0.4) / 0.6) = {n_dmg}")
    logger.info(f"  n_frags = max(0, ({r_frags} - 0.1) / 0.9) = {n_frags}")
    
    # Step 3 - PR value
    personal_rating = round(700 * n_dmg + 300 * n_frags + 150 * n_wins, 2)
    logger.info("")
    logger.info("Step 3 - PR:")
    logger.info(f"  700 * {n_dmg} = {700 * n_dmg}")
    logger.info(f"  300 * {n_frags} = {300 * n_frags}")
    logger.info(f"  150 * {n_wins} = {150 * n_wins}")
    logger.info(f"  SUM = {700 * n_dmg + 300 * n_frags + 150 * n_wins}")
    
    return personal_rating

def main(ship_id: int, ship_data: list):
    ship_stats = read_ship_stats(ship_id)
    result = calc_ship_rating_python(ship_data, ship_stats)

    logger.info("")
    logger.info(f"Personal Rating: {result}")


# 使用示例
if __name__ == "__main__":
    """测试 Rating 计算算法
    
    传入数据示例：ship_id,win_rate,avg_dmg,avg_frag

    使用示例：
    python tests/calc_rating.py -d 3655284688,56.3,106850,1.02
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--data",
        type=str,
        required=True,
        help="Index"
    )
    args = parser.parse_args()
    data = args.data
    split_data = data.split(',')
    if len(split_data) != 4:
        raise ValueError('Incorrect data')

    try:
        main(
            ship_id=int(split_data[0]),
            ship_data=[
                float(split_data[1]), 
                float(split_data[2]), 
                float(split_data[3])
            ]
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")