import os
import gzip
import json
import msgpack
import pymysql
from dotenv import load_dotenv


load_dotenv('.env.dev')

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USERNAME"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

file_path = r'F:/Kokomi_PJ_API/temp/'

def compress(data: dict):
    # 数据压缩
    if data:
        json_str = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":")  # 去空格，减小体积
        )
        json_bytes = json_str.encode("utf-8")
        return gzip.compress(json_bytes)
    else:
        return None

def load_mpk_gz(path: str) -> dict:
    with gzip.open(path, "rb") as f:
        data = msgpack.unpackb(f.read(), raw=False)
    return data

result = []

for root, dirs, files in os.walk(file_path):
    for name in files:
        if name.endswith(".mpk.gz"):
            path = os.path.join(root, name)

            datas = load_mpk_gz(path)

            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()

            for user_data in datas:
                region_id = user_data['id']['region']
                account_id = user_data['id']['account']
                str_id = f'{region_id}-{account_id}'
                if len(str_id) < 12:
                    str_id = str_id + ' '*(12-len(str_id))
                if user_data['base']['is_enabled'] == 0:
                    continue
                # 先检查用户id是否存在
                sql = "SELECT region_id FROM user_base WHERE region_id = %s AND account_id = %s;"
                cursor.execute(sql, [region_id, account_id])
                data = cursor.fetchone()
                if data is None:
                    dafault_name = f'User_{account_id}'
                    sql = """
                        INSERT INTO user_base (
                            region_id, 
                            account_id, 
                            username
                        ) VALUES (
                            %s, %s, %s
                        );
                    """
                    cursor.execute(sql,[region_id, account_id, dafault_name])
                    sql = """
                        INSERT INTO user_stats (
                            account_id
                        ) VALUES (
                            %s
                        );
                    """
                    cursor.execute(sql,[account_id])
                    sql = """
                        INSERT INTO user_clan (
                            account_id
                        ) VALUES (
                            %s
                        );
                    """
                    cursor.execute(sql,[account_id])
                    sql = """
                        INSERT INTO user_cache (
                            account_id
                        ) VALUES (
                            %s
                        );
                    """
                    cursor.execute(sql,[account_id])
                if user_data['clan'] != {}:
                    clan_id = user_data['clan']['id']
                    sql = "SELECT region_id FROM clan_base WHERE region_id = %s AND clan_id = %s;"
                    cursor.execute(sql, [region_id, clan_id])
                    data = cursor.fetchone()
                    if data is None:
                        sql = """
                            INSERT INTO clan_base (
                                region_id, 
                                clan_id, 
                                tag
                            ) VALUES (
                                %s, %s, %s
                            );
                        """
                        cursor.execute(sql,[region_id, clan_id, 'N/A'])
                        sql = """
                            INSERT INTO clan_stats (
                                clan_id 
                            ) VALUES (
                                %s
                            );
                        """
                        cursor.execute(sql,[clan_id])
                        sql = """
                            INSERT INTO clan_users (
                                clan_id 
                            ) VALUES (
                                %s
                            );
                        """
                        cursor.execute(sql,[clan_id])
                    sql = """
                        UPDATE user_clan 
                        SET 
                            clan_id = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(sql, [clan_id, account_id])
                if user_data['base']['is_public'] == 0:
                    sql = """
                        UPDATE user_base 
                        SET 
                            username = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE region_id = %s 
                            AND account_id = %s;
                    """
                    cursor.execute(
                        sql,[user_data['base']['username'], region_id, account_id]
                    )
                    sql = """
                        UPDATE user_stats 
                        SET 
                            is_enabled = 1, 
                            activity_level = 0, 
                            is_public = 0, 
                            total_battles = 0, 
                            pvp_battles = 0, 
                            ranked_battles = 0,
                            last_battle_at = NULL,
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(
                        sql,[account_id]
                    )
                else:
                    sql = """
                        UPDATE user_base 
                        SET 
                            username = %s, 
                            register_time = FROM_UNIXTIME(%s), 
                            insignias = %s, 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE region_id = %s 
                            AND account_id = %s;
                    """
                    cursor.execute(
                        sql,[user_data['base']['username'], user_data['base']['register_time'], user_data['base']['insignias'], region_id, account_id]
                    )
                    sql = """
                        UPDATE user_stats 
                        SET 
                            is_enabled = 1, 
                            activity_level = %s, 
                            is_public = 1, 
                            total_battles = %s, 
                            pvp_battles = %s, 
                            ranked_battles = %s, 
                            last_battle_at = FROM_UNIXTIME(%s), 
                            touch_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(
                        sql,
                        [
                            user_data['base']['activity_level'], user_data['base']['total_battles'], user_data['base']['pvp_battles'], user_data['base']['ranked_battles'],
                            user_data['base']['last_battle_at'] if user_data['base']['last_battle_at'] != 0 else None, account_id
                        ]
                    )
                    if user_data['brief'] != {}:
                        sql = """
                            UPDATE user_cache 
                            SET 
                                pvp_count = %s, 
                                win_rate = %s, 
                                avg_damage = %s, 
                                avg_frags = %s, 
                                max_damage = %s, 
                                max_damage_id = %s, 
                                max_exp = %s, 
                                max_exp_id = %s, 
                                cache = %s 
                            WHERE 
                                account_id = %s;
                        """
                        cursor.execute(
                            sql,[
                                user_data['brief']['battles_count'],
                                user_data['brief']['win_rate'],
                                user_data['brief']['avg_damage'],
                                user_data['brief']['avg_frags'],
                                user_data['brief']['max_damage'],
                                user_data['brief']['max_damage_id'],
                                user_data['brief']['max_exp'],
                                user_data['brief']['max_exp_id'],
                                compress(user_data['cache']),
                                account_id
                            ]
                        )
                conn.commit()
            cursor.close()
            conn.close()
            print(f'文件: {path} 数据写入数据库成功')