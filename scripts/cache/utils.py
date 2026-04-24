import json
import time
import random
import asyncio
import traceback
from tqdm import tqdm
from redis import Redis
from datetime import datetime
from httpx import AsyncClient
from pymysql import Connection
from pymysql.cursors import Cursor
from datetime import datetime, timezone

from logger import logger
from settings import (
    REGION,
    DATA_DIR, 
    VORTEX_API, 
    USE_TQDM,
    DATE_FMT,
    RANKING_BATTLES_LIMIT
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

async def fetch_data(async_client: AsyncClient, url: str):
    try:
        res = await async_client.get(url)
        requset_code = res.status_code
        requset_result = res.json()
        if requset_code == 200:
            # logger.debug(f'200 {url}')
            return requset_result['data']
        if requset_code == 404:
            # logger.debug(f'404 {url}')
            return {}
        # logger.warning(f'Code_{requset_code} {url}')
        return f'HTTP_STATUS_{requset_code}'
    except Exception as e:
        # logger.warning(f"{type(e).__name__} {url}")
        return f'ERROR_{type(e).__name__}'

def verify_responses(redis_client: Redis, responses: list):
    error = 0
    error_return = None
    now_time = now_iso()
    for response in responses:
        if isinstance(response, str):
            error += 1
            error_return = response
    key = f"metrics:http_total:{now_time[:10]}"
    redis_client.incrby(key, len(responses))
    if error == 0:
        return None
    else:
        key = f"metrics:http_error:{now_time[:10]}"
        redis_client.incrby(key, error)
        return error_return

def get_insignias(data: dict):
    if not data:
        return None
    keys = [
        "texture_id",
        "symbol_id",
        "border_color_id",
        "background_color_id",
        "background_id"
    ]
    if any(k not in data for k in keys):
        return None
    return "-".join(str(data[k]) for k in keys)

def get_content_class(
    value: float,
    thresholds: list
) -> int:
    for i in range(len(thresholds)):
        if value < thresholds[i]:
            return i + 1
    return 8

def get_version():
    file_path = DATA_DIR / f"json/game_version.json"
    with open(file_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
        return version_data['short']

def get_refresh(mysql_connection: Connection):
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                UNIX_TIMESTAMP(MAX(updated_at)) 
            FROM T_ship_stats_by_battles;;
        """
        cursor.execute(sql)
        return {
            'refresh': cursor.fetchone()[0]
        }
    except Exception as e:
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()

def calc_ship_rating(ship_data: list, server_data: list, metric_level: dict):
    # 获取服务器数据
    if server_data[0] is None or server_data[0] < 1000:
        return -1, -1, -1
    # 计算PR
    # Step 1 - ratios:
    r_wins = ship_data[0] / server_data[1]
    r_dmg = ship_data[1] / server_data[2]
    r_frags = ship_data[2] / server_data[3]
    # Step 2 - normalization:
    n_wins = max(0, (r_wins - 0.7) / (1 - 0.7))
    n_dmg = max(0, (r_dmg - 0.4) / (1 - 0.4))
    n_frags = max(0, (r_frags - 0.1) / (1 - 0.1))
    # Step 3 - PR value:
    personal_rating = round(700 * n_dmg + 300 * n_frags + 150 * n_wins, 2)
    damage_rating = get_content_class(r_dmg, metric_level[1])
    frags_rating = get_content_class(r_frags, metric_level[2])
    return personal_rating, damage_rating, frags_rating

def calc_recent_diff(old_cache: dict, latest_data: dict):
    """
    计算每艘船的近期增量数据（最新 - 本地缓存）
    """
    diff_data = {}
    for ship_id, new_values in latest_data.items():
        old_values = old_cache.get(ship_id, [0]*len(new_values))
        ship_diff = [new_val - old_val for new_val, old_val in zip(new_values, old_values)]
        ship_diff[-2] = ship_diff[-2] * 100
        ship_diff[-1] = ship_diff[-1] * 1000
        if any(d < 0 for d in ship_diff):
            continue
        if ship_diff[0] == 0:
            continue
        diff_data[ship_id] = ship_diff
    return diff_data

def read_metric_level(mysql_connection: Connection):
    cursor: Cursor = mysql_connection.cursor()
    try:
        result = {}
        for metric_id in [1, 2]:
            sql = """
                SELECT 
                    threshold
                FROM T_metric_level_thresholds
                WHERE metric_id = %s 
                ORDER BY id;
            """
            cursor.execute(sql, [metric_id])
            result[metric_id] = []
            for row in cursor.fetchall():
                result[metric_id].append(row[0])
        return result
    except Exception as e:
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()

def read_ship_record(mysql_connection: Connection):
    cursor: Cursor = mysql_connection.cursor()
    try:
        result = {}
        sql = """
            SELECT 
                ship_id,
                exp,
                exp_users,
                exp_user_id,
                frags,
                frags_users,
                frags_user_id,
                planes,
                planes_users,
                planes_user_id,
                damage,
                damage_users,
                damage_user_id,
                scouting_damage,
                scouting_damage_users,
                scouting_damage_user_id,
                potential_damage,
                potential_damage_users,
                potential_damage_user_id
            FROM T_ship_pvp_record;
        """
        cursor.execute(sql)
        for row in cursor.fetchall():
            result[str(row[0])] = [
                [row[1], row[2], row[3]], # exp
                [row[4], row[5], row[6]], # frags
                [row[7], row[8], row[9]], # planes
                [row[10], row[11], row[12]], # damage
                [row[13], row[14], row[15]], # scouting_damage
                [row[16], row[17], row[18]] # total_agro
            ]
        return result
    except Exception as e:
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()

def read_ship_data(mysql_connection: Connection):
    # 加载ship_info数据
    cursor: Cursor = mysql_connection.cursor()
    try:
        ship_info = {}
        sql = """
            SELECT 
                b.ship_id, 
                b.tier, 
                s.battles, 
                s.win_rate, 
                s.avg_damage, 
                s.avg_frags
            FROM T_ship_base b
            LEFT JOIN T_ship_stats_by_battles s
              ON b.ship_id = s.ship_id
            WHERE b.is_enabled = 1 
              AND b.is_old = 0
              AND b.tier > 5;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            ship_info[str(row[0])] = [
                row[1],
                [row[2],row[3],row[4],row[5]]
            ]
        return ship_info
    except Exception as e:
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()

def get_update_ids(mysql_connection: Connection):
    # 从数据库中批量读取并判断那些用户需要更新
    update_list = []
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                s.account_id
            FROM T_user_stats s
            LEFT JOIN T_user_pvp p 
              ON s.account_id = p.account_id
            WHERE 
                p.updated_at IS NULL
                OR (
                    s.is_enabled = 1
                    AND s.is_public = 1
                    AND s.pvp_battles <> p.battles
                );
        """
        cursor.execute(sql)
        update_list = [row[0] for row in cursor.fetchall()]
    except Exception:
        logger.error((f"{traceback.format_exc()}"))
    finally:
        cursor.close()
    return update_list

def refresh_user(mysql_connection: Connection, account_id: int, result: dict):
    return_msg = True
    user_data = {
        'is_enabled': 1,
        'is_public': 1,
        'total_battles': 0,
        'pve_battles': 0,
        'pvp_battles': 0,
        'ranked_battles': 0,
        'rating_battles': 0,
        'karma': 0,
        'last_battle_at': 0,
        'username': None,
        'register_time': None,
        'insignias': None
    }
    if result:
        result = result.get(str(account_id))
    if 'hidden_profile' in result:
        user_data['is_public'] = 0
        user_data['username'] = result['name']
    elif 'statistics' not in result:
        user_data['is_enabled'] = 0
    elif 'basic' not in result['statistics']:
        user_data['username'] = result['name']
        user_data['register_time'] = int(result['created_at'])
    else:
        leveling_points = result['statistics']['basic']['leveling_points']
        if leveling_points >= 1000000:
            leveling_points = leveling_points - 1000000
        user_data['username'] = result['name']
        user_data['register_time'] = int(result['created_at'])
        user_data['insignias'] = get_insignias(result['dog_tag'])
        user_data['total_battles'] = leveling_points
        user_data['karma'] = result['statistics']['basic']['karma']
        user_data['last_battle_at'] = result['statistics']['basic']['last_battle_time']
        user_data['pve_battles'] = 0 if result['statistics']['pve'] == {} else result['statistics']['pve']['battles_count']
        user_data['pvp_battles'] = 0 if result['statistics']['pvp'] == {} else result['statistics']['pvp']['battles_count']
        user_data['ranked_battles'] = 0 if result['statistics']['rank_solo'] == {} else result['statistics']['rank_solo']['battles_count']
        if REGION == 'ru':
            rating_count = 0
            rating_count += 0 if result['statistics']['rating_solo'] == {} else result['statistics']['rating_solo']['battles_count']
            rating_count += 0 if result['statistics']['rating_div'] == {} else result['statistics']['rating_div']['battles_count']
            user_data['rating_battles'] = rating_count
    mysql_connection.begin()
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                username, 
                UNIX_TIMESTAMP(updated_at) 
            FROM T_user_base 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [account_id])
        data = cursor.fetchone()
        # 过滤并防止脏数据污染
        if data:
            # 单独处理用户名称，部分账号有名称但无数据
            if user_data['username']:
                if user_data['register_time'] == None:
                    # 有名称但无注册时间 -> 隐藏战绩用户
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            username = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(
                        sql,[user_data['username'], account_id]
                    )
                else:
                    # 有名称和注册时间 -> 正常用户
                    sql = """
                        UPDATE T_user_base 
                        SET 
                            username = %s, 
                            register_time = FROM_UNIXTIME(%s), 
                            insignias = %s, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE account_id = %s;
                    """
                    cursor.execute(
                        sql,[user_data['username'], user_data['register_time'], user_data['insignias'], account_id]
                    )
                # 如果用户名称和刷新前不一致，则判定用户存在修改昵称行为
                if data[1] and data[0] != user_data['username']:
                    sql = """
                        INSERT INTO T_user_action (
                            account_id, 
                            username
                        ) VALUES (
                            %s, %s
                        );
                    """
                    cursor.execute(
                        sql,[account_id, data[0]]
                    )
            if user_data['is_enabled'] == 0:
                # 账号不存在（404）
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 0, 
                        activity_level = 0, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [account_id])
            elif user_data['is_public'] == 0:
                # 账号隐藏战绩
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 1, 
                        is_public = 0, 
                        activity_level = 0, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [account_id])
            else:
                # 正常账号
                last_battle_time = user_data['last_battle_at'] if user_data['last_battle_at'] != 0 else None
                sql = """
                    UPDATE T_user_stats 
                    SET 
                        is_enabled = 1,  
                        is_public = 1, 
                        activity_level = F_user_activity_level(%s),
                        total_battles = %s, 
                        pve_battles = %s, 
                        pvp_battles = %s, 
                        ranked_battles = %s, 
                        rating_battles = %s, 
                        karma = %s, 
                        last_battle_at = FROM_UNIXTIME(%s), 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE account_id = %s;
                """
                cursor.execute(
                    sql,
                    [
                        last_battle_time, 
                        user_data['total_battles'], 
                        user_data['pve_battles'], 
                        user_data['pvp_battles'], 
                        user_data['ranked_battles'], 
                        user_data['rating_battles'], 
                        user_data['karma'], 
                        last_battle_time, 
                        account_id
                    ]
                )
        else:
            return_msg = False
        mysql_connection.commit()
        return return_msg
    except Exception:
        mysql_connection.rollback()
        logger.error((f"{traceback.format_exc()}"))
        return False
    finally:
        cursor.close()

def refresh_leaderboard(
    mysql_connection: Connection, 
    redis_client: Redis,
    ship_ids: list
):
    redis_client.set(f'leaderboard:maintenance', 1, ex=3600)
    len_ship_ids = len(ship_ids)
    if USE_TQDM:
        iterator = tqdm(
            ship_ids, 
            total=len_ship_ids, 
            desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Refreshing MySQL"
        )
    else:
        iterator = enumerate(ship_ids, 1)
    for item in iterator:
        mysql_connection.begin()
        cursor: Cursor = mysql_connection.cursor()
        try:
            if USE_TQDM:
                update_id = item
                index = iterator.n
            else:
                index, update_id = item
            sql = """
                UPDATE T_ship_pvp_leaderboard l
                JOIN T_ship_stats_by_battles s 
                    ON l.ship_id = s.ship_id
                SET
                    l.rating = F_calculate_ship_pr(
                        l.win_rate, l.avg_damage, l.avg_frags,
                        s.win_rate, s.avg_damage, s.avg_frags
                    ),
                    l.avg_damage_level = F_get_metric_level(1, l.avg_damage, s.avg_damage),
                    l.avg_frags_level = F_get_metric_level(2, l.avg_frags, s.avg_frags),
                    l.updated_at = NOW()
                WHERE l.ship_id = %s;
            """
            cursor.execute(sql, [update_id])
            row_count = cursor.rowcount
            if USE_TQDM:
                iterator.set_postfix_str(f"{update_id} | UPDATE {row_count} Rows")
            else:
                logger.info(f'[{index}/{len_ship_ids}] {update_id} | UPDATE {row_count} Rows')
            mysql_connection.commit()
        except Exception as e:
            mysql_connection.rollback()
            logger.error((f"{traceback.format_exc()}"))
            redis_client.delete(f'leaderboard:maintenance')
            return type(e).__name__
        finally:
            cursor.close()
    if USE_TQDM:
        iterator = tqdm(
            ship_ids, 
            total=len_ship_ids, 
            desc=f"{datetime.now().strftime(DATE_FMT)} [INFO] Refreshing Redis"
        )
    else:
        iterator = enumerate(ship_ids, 1)
    for item in iterator:
        cursor: Cursor = mysql_connection.cursor()
        try:
            if USE_TQDM:
                update_id = item
                index = iterator.n
            else:
                index, update_id = item
            sql = """
                SELECT 
                    account_id, 
                    rating
                FROM T_ship_pvp_leaderboard
                WHERE ship_id = %s;
            """
            cursor.execute(sql, [update_id])
            rows = cursor.fetchall()
            if rows:
                key = f"leaderboard:ship:{update_id}"
                pipe = redis_client.pipeline()
                pipe.delete(key)
                for acc, rating in rows:
                    if rating >= 0:
                        pipe.zadd(key, {str(acc): float(rating)})
                pipe.execute()
                row_count = len(rows)
            else:
                row_count = 0
            if USE_TQDM:
                iterator.set_postfix_str(f"{update_id} | REFRESH {row_count} Keys")
            else:
                logger.info(f'[{index}/{len_ship_ids}] {update_id} | REFRESH {row_count} Keys')
            mysql_connection.commit()
        except Exception as e:
            mysql_connection.rollback()
            logger.error((f"{traceback.format_exc()}"))
            redis_client.delete(f'leaderboard:maintenance')
            return type(e).__name__
        finally:
            cursor.close()
    redis_client.delete(f'leaderboard:maintenance')
    redis_client.set(f'leaderboard:refresh_time', int(time.time()))
    return 'Success'
    
async def update_user_cache(
    mysql_connection: Connection, 
    redis_client: Redis, 
    async_client: AsyncClient,
    account_id: int, 
    game_version: str,
    ship_record: dict,
    ship_info: dict,
    metric_level: dict
):
    redis_key = f"token:ac:{account_id}"
    result = redis_client.get(redis_key)
    if result:
        ac = json.loads(result)
    else:
        ac = None
    base_url = random.choice(VORTEX_API)
    urls = [
        f'{base_url}/api/accounts/{account_id}/' + (f'?ac={ac}' if ac else ''),
        f'{base_url}/api/accounts/{account_id}/ships/' + (f'?ac={ac}' if ac else ''),
        f'{base_url}/api/accounts/{account_id}/ships/pvp/' + (f'?ac={ac}' if ac else '')
    ]
    tasks = [fetch_data(async_client, url) for url in urls]
    responses = await asyncio.gather(*tasks)
    error = verify_responses(redis_client, responses)
    if error != None:
        return error
    add_count = None
    overall = {}
    loacl_cache = None
    ship_pvp_cache = {}
    ship_pvp_record = {}
    ship_ranking_cache = {}
    basic_data = responses[0]
    refresh_result = refresh_user(mysql_connection, account_id, basic_data)
    if not refresh_result:
        return 'Refresh Error'
    if basic_data:
        basic_data = basic_data.get(str(account_id))
    # 隐藏战绩或无数据
    if (
        basic_data == None or
        'hidden_profile' in basic_data or
        'statistics' not in basic_data or 
        'pvp' not in basic_data['statistics'] or 
        basic_data['statistics']['pvp'].get('battles_count', 0) == 0
    ):
        mysql_connection.begin()
        cursor: Cursor = mysql_connection.cursor()
        try:
            sql = """
                UPDATE T_user_pvp 
                SET 
                    battles = 0, 
                    win_rate = 0, 
                    avg_damage = 0, 
                    avg_frags = 0,  
                    avg_exp = 0, 
                    ship_cache = NULL, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE 
                    account_id = %s;
            """
            cursor.execute(
                sql,[account_id]
            )
            sql = """
                UPDATE T_user_pvp_record 
                SET 
                    max_exp = 0, 
                    max_exp_id = NULL, 
                    max_damage = 0, 
                    max_damage_id = NULL, 
                    max_frags = 0, 
                    max_frags_id = NULL, 
                    max_planes_killed = 0, 
                    max_planes_killed_id = NULL, 
                    max_scouting_damage = 0, 
                    max_scouting_damage_id = NULL, 
                    max_potential_damage = 0, 
                    max_potential_damage_id = NULL, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE 
                    account_id = %s;
            """
            cursor.execute(
                sql,[account_id]
            )
            mysql_connection.commit()
            return 'NoData or Hidden'
        except Exception as e:
            mysql_connection.rollback()
            logger.error((f"{traceback.format_exc()}"))
            return type(e).__name__
        finally:
            cursor.close()
    pvp_count = basic_data['statistics']['pvp'].get('battles_count')
    overall = {
        'battles_count': pvp_count,
        'win_rate': round(basic_data['statistics']['pvp']['wins']/pvp_count*100,4),
        'avg_damage': round(basic_data['statistics']['pvp']['damage_dealt']/pvp_count,2),
        'avg_frags': round(basic_data['statistics']['pvp']['frags']/pvp_count,4),
        'avg_exp': round(basic_data['statistics']['pvp']['original_exp']/pvp_count,2)
    }
    record = [
        basic_data['statistics']['pvp']['max_exp'],
        basic_data['statistics']['pvp']['max_exp_vehicle'],
        basic_data['statistics']['pvp']['max_damage_dealt'],
        basic_data['statistics']['pvp']['max_damage_dealt_vehicle'],
        basic_data['statistics']['pvp']['max_frags'],
        basic_data['statistics']['pvp']['max_frags_vehicle'],
        basic_data['statistics']['pvp']['max_planes_killed'],
        basic_data['statistics']['pvp']['max_planes_killed_vehicle'],
        basic_data['statistics']['pvp']['max_scouting_damage'],
        basic_data['statistics']['pvp']['max_scouting_damage_vehicle'],
        basic_data['statistics']['pvp']['max_total_agro'],
        basic_data['statistics']['pvp']['max_total_agro_vehicle']
    ]
    ships_data = responses[1][str(account_id)]['statistics']
    pvp_data = responses[2][str(account_id)]['statistics']
    for ship_id in pvp_data.keys():
        ship_data = pvp_data[ship_id]['pvp']
        if ship_data == {}:
            continue
        ship_pvp_cache[ship_id]=[
            ship_data['battles_count'],
            ship_data['wins'],
            ship_data['damage_dealt'],
            ship_data['frags'],
            ship_data['original_exp'],
            ship_data['survived'],
            max(
                ship_data.get('assist_damage', 0),
                ship_data.get('scouting_damage', 0)
            )  // 100,    # 注意单位
            ship_data['art_agro'] // 1000    # 注意单位
        ]
        ship_pvp_record[ship_id]=[
            ship_data['max_exp'],
            ship_data['max_frags'],
            ship_data['max_planes_killed'],
            ship_data['max_damage_dealt'],
            ship_data['max_scouting_damage'],
            ship_data['max_total_agro']
        ]
    for ship_id in pvp_data.keys():
        ship_data = pvp_data[ship_id]['pvp']
        if ship_data == {}:
            continue
        if ship_id not in ship_info:
            continue
        ship_tier = ship_info[ship_id][0]
        battles_limit = RANKING_BATTLES_LIMIT.get(str(ship_tier))
        if ship_data['battles_count'] < battles_limit:
            continue
        battles_data = ships_data[ship_id]
        if 'pvp_solo' in battles_data and battles_data['pvp_solo'] != {}:
            solo_ratio = round(battles_data['pvp_solo']['battles_count']/battles_data['pvp']['battles_count']*100,4)
        else:
            solo_ratio = 0
        if ship_data['shots_by_main'] != 0:
            hit_ratio = round(ship_data['hits_by_main']/ship_data['shots_by_main']*100,2)
        else:
            hit_ratio = 0
        personal_rating, damage_rating, frags_rating = calc_ship_rating(
            ship_data=[
                round(ship_data['wins']/ship_data['battles_count']*100, 4),
                int(ship_data['damage_dealt']/ship_data['battles_count']),
                round(ship_data['frags']/ship_data['battles_count'], 2)
            ],
            server_data=ship_info[ship_id][1],
            metric_level=metric_level
        )
        ship_ranking_cache[ship_id]=[
            ship_data['battles_count'],
            personal_rating,
            round(ship_data['wins']/ship_data['battles_count']*100,4),
            solo_ratio,
            int(ship_data['damage_dealt']/ship_data['battles_count']),
            damage_rating,
            round(ship_data['frags']/ship_data['battles_count'],2),
            frags_rating,
            int(ship_data['original_exp']/ship_data['battles_count']),
            hit_ratio,
            ship_data['max_exp'],
            ship_data['max_damage_dealt']
        ]
    # 更新 T_user_pvp T_user_pvp_record T_ship_pvp_record T_ship_pvp_leaderboard 表
    mysql_connection.begin()
    cursor: Cursor = mysql_connection.cursor()
    try:
        sql = """
            SELECT 
                battles, 
                ship_cache 
            FROM T_user_pvp  
            WHERE account_id = %s;
        """
        cursor.execute(sql,[account_id])
        data = cursor.fetchone()
        if pvp_count != data[0] and data[0] != 0:
            loacl_cache = json.loads(data[1])
        sql = """
            UPDATE T_user_pvp 
            SET 
                battles = %s, 
                win_rate = %s, 
                avg_damage = %s, 
                avg_frags = %s, 
                avg_exp = %s, 
                ship_cache = %s, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE 
                account_id = %s;
        """
        cursor.execute(
            sql,[
                overall['battles_count'],
                overall['win_rate'],
                overall['avg_damage'],
                overall['avg_frags'],
                overall['avg_exp'],
                json.dumps(ship_pvp_cache),
                account_id
            ]
        )
        sql = """
            UPDATE T_user_pvp_record 
            SET 
                max_exp = %s, 
                max_exp_id = %s, 
                max_damage = %s, 
                max_damage_id = %s, 
                max_frags = %s, 
                max_frags_id = %s, 
                max_planes_killed = %s, 
                max_planes_killed_id = %s, 
                max_scouting_damage = %s, 
                max_scouting_damage_id = %s, 
                max_potential_damage = %s, 
                max_potential_damage_id = %s, 
                updated_at = CURRENT_TIMESTAMP 
            WHERE 
                account_id = %s;
        """
        cursor.execute(
            sql,record + [account_id]
        )
        fields = [
            ("exp", 0),
            ("frags", 1),
            ("planes", 2),
            ("damage", 3),
            ("scouting_damage", 4),
            ("potential_damage", 5),
        ]
        for ship_id, new_data in ship_pvp_record.items():
            ship_id_str = str(ship_id)
            old = ship_record.get(ship_id_str)
            if old is None:
                values = []
                params = [ship_id]
                for field, i in fields:
                    val = new_data[i]
                    if val > 0:
                        values.extend([val, 1, account_id])
                    else:
                        values.extend([0, 0, None])
                cursor.execute("""
                    INSERT INTO T_ship_pvp_record (
                        ship_id,
                        exp, exp_users, exp_user_id,
                        frags, frags_users, frags_user_id,
                        planes, planes_users, planes_user_id,
                        damage, damage_users, damage_user_id,
                        scouting_damage, scouting_damage_users, scouting_damage_user_id,
                        potential_damage, potential_damage_users, potential_damage_user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [ship_id] + values)
                cache = []
                for field, i in fields:
                    val = new_data[i]
                    if val > 0:
                        cache.append([val, 1, account_id])
                    else:
                        cache.append([0, 0, None])
                ship_record[ship_id_str] = cache
                continue
            update_parts = []
            params = []
            for idx, (field, i) in enumerate(fields):
                new_val = new_data[i]
                old_val, old_users, old_user_id = old[idx]
                if new_val > old_val:
                    update_parts.append(f"{field}=%s")
                    update_parts.append(f"{field}_users=1")
                    update_parts.append(f"{field}_user_id=%s")
                    params.extend([new_val, account_id])
                    old[idx] = [new_val, 1, account_id]
                elif new_val == old_val:
                    if new_val != 0:
                        new_users = (old_users or 0) + 1
                        update_parts.append(f"{field}_users=%s")
                        if new_users > 1:
                            update_parts.append(f"{field}_user_id=NULL")
                            old[idx] = [old_val, new_users, None]
                        else:
                            update_parts.append(f"{field}_user_id=%s")
                            old[idx] = [old_val, new_users, old_user_id]
                        params.append(new_users)
                        if new_users <= 1:
                            params.append(old_user_id)
            if update_parts:
                sql = f"""
                    UPDATE T_ship_pvp_record
                    SET 
                        {", ".join(update_parts)}
                    WHERE ship_id = %s;
                """
                params.append(ship_id)
                cursor.execute(sql, params)
        if ship_ranking_cache != {}:
            values_to_insert = []
            for ship_id, data in ship_ranking_cache.items():
                values_to_insert.append((
                    account_id,
                    ship_id,
                    data[0],     # battles
                    data[1],     # rating
                    data[2],     # win_rate
                    data[3],     # solo_rate
                    data[4],     # avg_damage
                    data[5],
                    data[6],     # avg_frags
                    data[7],
                    data[8],     # avg_exp
                    data[9],     # hit_ratio
                    data[10],    # max_exp
                    data[11]     # max_damage
                ))
            sql = """
                INSERT INTO T_ship_pvp_leaderboard (
                    account_id, ship_id, battles, rating, win_rate, solo_rate, 
                    avg_damage, avg_damage_level, avg_frags, avg_frags_level, avg_exp, hit_ratio, 
                    max_exp, max_damage, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
                ON DUPLICATE KEY UPDATE 
                    rating = VALUES(rating),
                    battles = VALUES(battles),
                    rating = VALUES(rating),
                    win_rate = VALUES(win_rate),
                    solo_rate = VALUES(solo_rate),
                    avg_damage = VALUES(avg_damage),
                    avg_damage_level = VALUES(avg_damage_level),
                    avg_frags = VALUES(avg_frags),
                    avg_frags_level = VALUES(avg_frags_level),
                    avg_exp = VALUES(avg_exp),
                    hit_ratio = VALUES(hit_ratio),
                    max_exp = VALUES(max_exp),
                    max_damage = VALUES(max_damage),
                    updated_at = CURRENT_TIMESTAMP;
            """
            cursor.executemany(sql, values_to_insert)
        if loacl_cache:
            add_count = 0
            diff_data = calc_recent_diff(loacl_cache, ship_pvp_cache)
            recent_data = {}
            insert_data = {}
            update_data = {}
            cursor.execute("""
                SELECT 
                    ship_id, battles, wins, damage, frags, exp,
                    survived, scouting_damage, potential_damage
                FROM T_ship_stats_by_recent_archive
                WHERE game_version = %s
            """, [game_version])
            for row in cursor.fetchall():
                ship_id = row[0]
                recent_data[str(ship_id)] = list(row[1:])
            for ship_id, diff_values in diff_data.items():
                if ship_id in recent_data:
                    update_data[ship_id] = [
                        r + d for r, d in zip(recent_data[ship_id], diff_values)
                    ]
                else:
                    insert_data[ship_id] = diff_values
                add_count += 1
            if insert_data != {}:
                insert_sql = """
                    INSERT INTO T_ship_stats_by_recent_archive (
                        ship_id, game_version,
                        battles, wins, damage, frags, exp,
                        survived, scouting_damage, potential_damage
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    );
                """
                insert_values = [
                    (
                        ship_id,
                        game_version,
                        *values
                    )
                    for ship_id, values in insert_data.items()
                ]
                cursor.executemany(insert_sql, insert_values)
            if update_data != {}:
                update_sql = """
                    UPDATE T_ship_stats_by_recent_archive
                    SET
                        battles = %s,
                        wins = %s,
                        damage = %s,
                        frags = %s,
                        exp = %s,
                        survived = %s,
                        scouting_damage = %s,
                        potential_damage = %s
                    WHERE ship_id = %s 
                    AND game_version = %s;
                """
                update_values = [
                    (
                        *values,
                        ship_id,
                        game_version
                    )
                    for ship_id, values in update_data.items()
                ]
                cursor.executemany(update_sql, update_values)
        mysql_connection.commit()
    except Exception as e:
        mysql_connection.rollback()
        logger.error((f"{traceback.format_exc()}"))
        return type(e).__name__
    finally:
        cursor.close()
    # 写redis
    if ship_ranking_cache != {}:
        pipe = redis_client.pipeline()
        for ship_id, values in ship_ranking_cache.items():
            key = f"leaderboard:ship:{ship_id}"
            pipe.zadd(key, {str(account_id): values[1]})
        pipe.execute()
    return 'Success' + (f' +{add_count}' if add_count else '')