import traceback
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from pymysql.cursors import Cursor

from logger import logger
from settings import METRIC_MAPPING
from api import fetch_user_pvp_data
from syncer import UserStatsSyncer
from utils import calc_recent_diff, calc_ship_rating
from db_ops import (
    get_local_cache,
    handle_hidden_profile,
    update_user_pvp,
    update_user_pvp_record,
    upsert_ship_pvp_record,
    upsert_leaderboard,
    insert_recent_diff_data,
    update_redis_leaderboard
)


def extract_overall_stats(basic_data: dict) -> dict:
    """提取用户总体统计数据"""
    pvp_count = basic_data['statistics']['pvp'].get('battles_count')
    return {
        'battles_count': pvp_count,
        'win_rate': round(basic_data['statistics']['pvp']['wins'] / pvp_count * 100, 4),
        'avg_damage': round(basic_data['statistics']['pvp']['damage_dealt'] / pvp_count, 2),
        'avg_frags': round(basic_data['statistics']['pvp']['frags'] / pvp_count, 4),
        'avg_exp': round(basic_data['statistics']['pvp']['original_exp'] / pvp_count, 2)
    }

def extract_record_stats(basic_data: dict) -> list:
    """提取用户最高记录数据"""
    pvp = basic_data['statistics']['pvp']
    return [
        pvp.get('max_exp', 0),
        pvp.get('max_exp_vehicle'),
        pvp.get('max_damage_dealt', 0),
        pvp.get('max_damage_dealt_vehicle'),
        pvp.get('max_frags', 0),
        pvp.get('max_frags_vehicle'),
        pvp.get('max_planes_killed', 0),
        pvp.get('max_planes_killed_vehicle'),
        pvp.get('max_scouting_damage', 0),
        pvp.get('max_scouting_damage_vehicle'),
        pvp.get('max_total_agro', 0),
        pvp.get('max_total_agro_vehicle')
    ]

def build_ship_pvp_cache(pvp_data: dict) -> dict:
    """构建船只PVP缓存数据"""
    ship_pvp_cache = {}
    for ship_id, ship_data in pvp_data.items():
        pvp = ship_data.get('pvp', {})
        if not pvp:
            continue
        
        ship_pvp_cache[ship_id] = [
            pvp.get('battles_count', 0),
            pvp.get('wins', 0),
            pvp.get('damage_dealt', 0),
            pvp.get('frags', 0),
            pvp.get('original_exp', 0),
            pvp.get('survived', 0),
            max(pvp.get('assist_damage', 0), pvp.get('scouting_damage', 0)) // 100,  # 注意单位
            pvp.get('art_agro', 0) // 1000  # 注意单位
        ]
    return ship_pvp_cache

def update_ship_records(
    ship_record: dict, 
    ship_pvp_cache: dict, 
    account_id: int
) -> list:
    """
    更新船只记录
    
    Args:
        ship_record: 船只记录字典（会被直接修改）
        ship_pvp_cache: 船只PVP缓存数据
        account_id: 用户ID
    
    Returns:
        updated_record: 需要更新的记录列表
    """
    updated_record = []
    
    for ship_id in ship_pvp_cache.keys():
        if ship_id not in ship_record:
            continue
        
        for idx, (metric_id, data_key) in enumerate(METRIC_MAPPING):
            # 从 ship_pvp_cache 中获取用户该指标的最大值
            ship_data = ship_pvp_cache.get(ship_id, {})
            if isinstance(ship_data, dict):
                user_value = ship_data.get(data_key, 0)
            else:
                # 如果 ship_pvp_cache[ship_id] 是列表，需要根据实际结构调整
                continue
            
            current = ship_record[ship_id][idx]
            
            if user_value > current[0]:
                logger.debug(f'{current} -> {[user_value, 1, account_id]}')
                ship_record[ship_id][idx] = [user_value, 1, account_id]
                updated_record.append((int(ship_id), metric_id, user_value, 1, account_id))
            elif user_value == current[0] and user_value > 0:
                new_users_count = current[1] + 1
                logger.debug(f'{current} -> {[current[0], new_users_count, None]}')
                ship_record[ship_id][idx] = [current[0], new_users_count, None]
                updated_record.append((int(ship_id), metric_id, current[0], new_users_count, None))
    
    return updated_record

def build_ranking_cache(
    pvp_data: dict, 
    ships_data: dict, 
    ship_info: dict
) -> dict:
    """构建船只排行榜缓存数据"""
    ship_ranking_cache = {}
    
    for ship_id, ship_data in pvp_data.items():
        pvp = ship_data.get('pvp', {})
        if not pvp:
            continue
        
        if ship_id not in ship_info:
            continue
        
        battles_limit = ship_info[ship_id][0]
        if pvp.get('battles_count', 0) < battles_limit:
            continue
        
        battles_data = ships_data.get(ship_id, {})
        
        # 计算 solo 比例
        if 'pvp_solo' in battles_data and battles_data['pvp_solo']:
            solo_ratio = round(
                battles_data['pvp_solo']['battles_count'] / battles_data['pvp']['battles_count'] * 100, 4
            )
        else:
            solo_ratio = 0
        
        # 计算命中率
        shots = pvp.get('shots_by_main', 0)
        hits = pvp.get('hits_by_main', 0)
        hit_ratio = round(hits / shots * 100, 2) if shots != 0 else 0
        
        # 计算评分
        personal_rating, damage_rating, frags_rating = calc_ship_rating(
            ship_data=[
                round(pvp['wins'] / pvp['battles_count'] * 100, 4),
                int(pvp['damage_dealt'] / pvp['battles_count']),
                round(pvp['frags'] / pvp['battles_count'], 2)
            ],
            server_data=ship_info[ship_id][1]
        )
        
        ship_ranking_cache[ship_id] = [
            pvp['battles_count'],
            personal_rating,
            round(pvp['wins'] / pvp['battles_count'] * 100, 4),
            solo_ratio,
            int(pvp['damage_dealt'] / pvp['battles_count']),
            damage_rating,
            round(pvp['frags'] / pvp['battles_count'], 2),
            frags_rating,
            int(pvp['original_exp'] / pvp['battles_count']),
            hit_ratio,
            pvp.get('max_exp', 0),
            pvp.get('max_damage_dealt', 0)
        ]
    
    return ship_ranking_cache

def _is_invalid_or_hidden_profile(basic_data: dict) -> bool:
    """检查用户是否为无效账号或隐藏战绩"""
    if basic_data is None:
        return True
    if 'hidden_profile' in basic_data:
        return True
    if 'statistics' not in basic_data:
        return True
    if 'pvp' not in basic_data['statistics']:
        return True
    if basic_data['statistics']['pvp'].get('battles_count', 0) == 0:
        return True
    return False

async def update_user_cache(
    mysql_connection: Connection,
    redis_client: Redis,
    async_client: AsyncClient,
    account_id: int,
    ship_record: dict,
    ship_info: dict
) -> None:
    """更新用户缓存数据 - 主入口函数
    
    - 调用fetch_user_pvp_data()获取API数据
    - 刷新用户基础信息（用户名、注册时间等）
    - 更新PVP总体统计
    - 更新船只的最高记录
    - 更新船只排行榜数据
    - 记录近期数据变化
    """
    # 获取用户PVP数据
    try:
        responses = await fetch_user_pvp_data(async_client, redis_client, account_id)
        if responses is None:
            logger.error(f'{account_id} | Fetch data failed')
        
        ship_pvp_cache = {}
        update_record_list = []
        ship_ranking_cache = {}
        
        basic_data = responses[0]
        
        # 刷新用户基础信息
        refresh_result = UserStatsSyncer.refresh(mysql_connection, account_id, basic_data)
        if refresh_result:
            logger.error(f'{account_id} | Refresh failed: {refresh_result}')
            return
        
        if basic_data:
            basic_data = basic_data.get(str(account_id))
        
        # 处理隐藏战绩或无数据的用户
        if _is_invalid_or_hidden_profile(basic_data):
            handel_result = handle_hidden_profile(mysql_connection, account_id)
            if handel_result:
                logger.error(f'{account_id} (Hidden) | Refresh failed: {refresh_result}')
                return
            else:
                return
        
        # 提取统计数据
        overall = extract_overall_stats(basic_data)
        record = extract_record_stats(basic_data)
        
        # 构建船只PVP缓存
        pvp_data = responses[2][str(account_id)]['statistics']
        ship_pvp_cache = build_ship_pvp_cache(pvp_data)
        
        # 更新船只记录
        update_record_list = update_ship_records(ship_record, ship_pvp_cache, account_id)
        
        # 构建排行榜缓存
        ships_data = responses[1][str(account_id)]['statistics']
        ship_ranking_cache = build_ranking_cache(pvp_data, ships_data, ship_info)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f'{account_id} | Data processing error: {type(e).__name__}')
        return

    # 数据库更新或者写入操作
    try:
        cursor: Cursor = mysql_connection.cursor()
        
        # 获取本地缓存
        local_cache = get_local_cache(cursor, account_id)
        
        # 更新各项数据
        update_user_pvp(cursor, account_id, overall, ship_pvp_cache)
        update_user_pvp_record(cursor, account_id, record)
        upsert_ship_pvp_record(cursor, update_record_list)
        upsert_leaderboard(cursor, ship_ranking_cache, account_id)
        
        # 处理近期数据变化
        if local_cache:
            diff_data = calc_recent_diff(local_cache, ship_pvp_cache)
            insert_recent_diff_data(cursor, diff_data, account_id)
        
        mysql_connection.commit()
        
    except Exception as e:
        mysql_connection.rollback()
        logger.error(traceback.format_exc())
        logger.error(f'{account_id} | Update database failed: {type(e).__name__}')
        return
    finally:
        if cursor:
            cursor.close()
    
    # 更新 Redis
    try:
        update_redis_leaderboard(redis_client, ship_ranking_cache, account_id)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f'{account_id} | Refresh redis failed: {type(e).__name__}')
    
    return 