import os
import json
import pymysql
import requests
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('env.dev')
DATA_DIR = Path(os.getenv("DATA_DIR"))
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}
REALM_MAP = {
    'asia': 'sg', 
    'eu': 'eu', 
    'na': 'us', 
    'ru': 'ru', 
    'cn': 'cn360' 
}
LEAGUE_LIST = [
    [0,1], [1,1], [1,2], [1,3],
    [2,1], [2,2], [2,3], [3,1],
    [3,2], [3,3], [4,1], [4,2],
    [4,3]
]
CLAN_COLOR_INDEX = {
    13477119: 0,
    12511165: 1,
    14931616: 2,
    13427940: 3,
    13408614: 4,
    11776947: 5,
}

def fetch_data(url: str, params: dict = None):
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            print(f'OK_200 {url}')
            result = resp.json()
            return result
        print(f'Code_{resp.status_code} {url}')
        return []
    except Exception as e:
        print(f"{type(e).__name__} {url}")
        return []

def get_clan_rank_data(region: str, clan_api: str):
    clan_data_list = []
    realm = REALM_MAP.get(region)
    for i in range(13):
        league=LEAGUE_LIST[i][0]
        division=LEAGUE_LIST[i][1]
        url = f'{clan_api}/api/ladder/structure/' 
        params = {
            'realm': realm,
            'league': league,
            'division': division,
            'limit': 1000
        }
        result = fetch_data(url, params)
        for temp_data in result:
            clan_data_list.append([
                temp_data['id'],
                temp_data['tag'],
                temp_data['league']
            ])
    return clan_data_list

def main():
    file_path = DATA_DIR / 'json/init_marker.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        REGION: str = data['region']
    file_path = DATA_DIR / 'json/endpoints.json'
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        CLAN_API: str = data['clan_api']
    total_list = get_clan_rank_data(REGION, CLAN_API)
    print(f'Regional clan: {len(total_list)}')
    conn = pymysql.connect(**MYSQL_CONFIG)
    add_clan = 0
    conn.begin()
    cursor = conn.cursor()
    try:
        for clan_data in total_list:
            sql = """
                SELECT 
                    clan_id 
                FROM clan_base 
                WHERE clan_id = %s;
            """
            cursor.execute(sql, [clan_data[0]])
            clan = cursor.fetchone()
            if clan is None:
                sql = """
                    INSERT INTO clan_base (
                        clan_id, 
                        tag, 
                        league, 
                        touch_at
                    ) VALUES (
                        %s, %s, %s, CURRENT_TIMESTAMP
                    );
                """
                cursor.execute(sql, [clan_data[0],clan_data[1],clan_data[2]])
                sql = """
                    INSERT INTO clan_users (
                        clan_id
                    ) VALUES (
                        %s
                    );
                """
                cursor.execute(sql, [clan_data[0]])
                add_clan += 1
        conn.commit()
    except Exception:
        conn.rollback()
        print(f"{traceback.format_exc()}")
    finally:
        cursor.close()
    print(f"Add clan: {add_clan}")


if __name__ == "__main__":
    main()