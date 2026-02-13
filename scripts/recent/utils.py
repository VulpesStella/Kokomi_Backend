import time
import json
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor

from logger import logger
from settings import BATCH_SIZE


def get_update_ids(conn: Connection, redis_client: Redis):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                MAX(id) 
            FROM recent;
        """
        cursor.execute(sql)
        data = cursor.fetchone()
        max_id = data[0]
        logger.info(f'Max ID: {max_id}')
        for offset in range(0, max_id, BATCH_SIZE):
            sql = """
                SELECT 
                    r.region_id, 
                    r.account_id,  
                    r.enable_recent, 
                    r.enable_daily, 
                    s.total_battles 
                FROM recent AS r 
                LEFT JOIN user_stats AS s 
                    ON r.account_id = s.account_id 
                WHERE r.id BETWEEN %s AND %s;
            """
            cursor.execute(sql, [offset+1, offset+BATCH_SIZE])
            rows = cursor.fetchall()
            for row in rows:
                if row is None:
                    continue
                region_id = row[0]
                account_id = row[1]
                if row[2] == 1:
                    redis_key = f"token:ac:{account_id}"
                    result = redis_client.get(redis_key)
                    if result:
                        result = json.loads(result)
                        ac = result.get('ac')
                    else:
                        ac = None
                update_list.append([region_id, account_id, row[3], row[4], ac])
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

def del_recent(conn: Connection, region_id: int ,account_id: int):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            UPDATE recent 
            SET
                enable_recent = 0, 
                enable_daily = 0 
            FROM recent 
            WHERE region_id = %s 
              AND account_id = %s;
        """
        cursor.execute(sql, [region_id, account_id])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def del_recents(conn: Connection, region_id: int ,account_id: int):
    conn.begin()
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            UPDATE recent 
            SET
                enable_daily = 0 
            FROM recent 
            WHERE region_id = %s 
              AND account_id = %s;
        """
        cursor.execute(sql, [region_id, account_id])
        sql = """
            SELECT 
                id 
            FROM user_base 
            WHERE region_id = %s 
                AND account_id = %s;
        """
        cursor.execute(sql,[region_id,account_id])
        data = cursor.fetchone()
        game_id = data[0]
        sql = """
            DELETE FROM recent_pro 
            WHERE game_id = %s;
        """
        cursor.execute(sql, [game_id])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()

def get_activity_level(is_public: bool, total_battles: int = 0, last_battle_time: int = 0):
        "获取activity_level"
        if not is_public:
            return 0
        if total_battles == 0 or last_battle_time == 0:
            return 1
        current_timestamp = int(time.time())
        time_differences = [
            (1 * 24 * 60 * 60, 2),
            (3 * 24 * 60 * 60, 3),
            (7 * 24 * 60 * 60, 4),
            (30 * 24 * 60 * 60, 5),
            (90 * 24 * 60 * 60, 6),
            (180 * 24 * 60 * 60, 7),
            (360 * 24 * 60 * 60, 8),
        ]
        time_since_last_battle = current_timestamp - last_battle_time
        for time_limit, return_value in time_differences:
            if time_since_last_battle <= time_limit:
                return return_value
        return 9

def get_insignias(data: dict):
    if data is None or data == {}:
        return None
    else:
        return f"{data['texture_id']}-{data['symbol_id']}-{data['border_color_id']}-{data['background_color_id']}-{data['background_id']}"

def update_base(conn: Connection, region_id: int ,account_id: int, user_basic: dict):
    refresh_data = {
        'is_enabled': 0,
        'activity_level': 0,
        'is_public': 0,
        'username': "",
        'register_time': None,
        'insignias': None,
        'total_battles': 0,
        'pvp_battles': 0,
        'ranked_battles': 0,
        'last_battle_at': 0
    }
    if user_basic:
            user_basic = user_basic[str(account_id)]
    if 'hidden_profile' in user_basic:
        refresh_data['is_enabled'] = 1
        refresh_data['is_public'] = 0
        refresh_data['activity_level'] = get_activity_level(is_public=0)
        refresh_data['username'] = user_basic['name']
    elif (
        user_basic == None or user_basic == {} or
        'statistics' not in user_basic or 
        'basic' not in user_basic['statistics'] or 
        user_basic['statistics']['basic']['leveling_points'] == 0
    ):
        refresh_data['is_enabled'] = 0
    else:
        refresh_data['is_enabled'] = 1
        refresh_data['is_public'] = 1
        refresh_data['activity_level'] = get_activity_level(
            is_public=1,
            total_battles=user_basic['statistics']['basic']['leveling_points'],
            last_battle_time=user_basic['statistics']['basic']['last_battle_time']
        )
        if region_id == 4:
            ranked_count = 0
            ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
            ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
        else:
            ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
        refresh_data['username'] = user_basic['name']
        refresh_data['register_time'] = user_basic['statistics']['basic']['created_at']
        refresh_data['insignias'] = get_insignias(user_basic['dog_tag'])
        refresh_data['total_battles'] = user_basic['statistics']['basic']['leveling_points']
        refresh_data['pvp_battles'] = 0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count']
        refresh_data['ranked_battles'] = ranked_count
        refresh_data['last_battle_at'] = user_basic['statistics']['basic']['last_battle_time']
    cursor: Cursor = conn.cursor()
    try:
        sql = """
            SELECT 
                username, 
                UNIX_TIMESTAMP(register_time) AS register_time, 
                insignias 
            FROM user_base 
            WHERE region_id = %s 
                AND account_id = %s;
        """
        cursor.execute(sql, [region_id, account_id])
        result = cursor.fetchone()
        if refresh_data['is_enabled'] == 0:
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [refresh_data['is_enabled'], account_id])
        elif refresh_data['is_public'] == 0:
            sql = """
                UPDATE user_base 
                SET 
                    username = %s, 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE region_id = %s 
                    AND account_id = %s;
            """
            cursor.execute(sql, [refresh_data['username'], region_id, account_id])
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    activity_level = %s, 
                    is_public = %s, 
                    total_battles = 0, 
                    pvp_battles = 0, 
                    ranked_battles = 0,
                    last_battle_at = NULL,
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [refresh_data['is_enabled'], refresh_data['activity_level'], refresh_data['is_public'], account_id])
        else:
            if (
                result[0] != refresh_data['username'] or
                result[1] != refresh_data['register_time'] or
                result[2] != refresh_data['insignias']
            ):
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
                cursor.execute(sql, [refresh_data['username'],refresh_data['register_time'],refresh_data['insignias'],region_id,account_id])
            sql = """
                UPDATE user_stats 
                SET 
                    is_enabled = %s, 
                    activity_level = %s, 
                    is_public = %s, 
                    total_battles = %s, 
                    pvp_battles = %s, 
                    ranked_battles = %s, 
                    last_battle_at = FROM_UNIXTIME(%s), 
                    touch_at = CURRENT_TIMESTAMP 
                WHERE account_id = %s;
            """
            cursor.execute(sql, [
                refresh_data['is_enabled'],refresh_data['activity_level'],refresh_data['is_public'],
                refresh_data['total_battles'],refresh_data['pvp_battles'],refresh_data['ranked_battles'],
                refresh_data['last_battle_at'],account_id
            ])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
