import requests
from redis import Redis
from typing import Optional, Union

from logger import logger
from settings import CLAN_API
from utils import (
    get_current_iso_time, 
    formtime_to_timestamp
)


def fetch_data(url: str) -> Union[dict, str]:
    """发送 GET 请求并解析 JSON 响应

    Args:
        url: 请求地址

    Returns:
        成功时返回解析后的 dict，失败时返回错误标识字符串（如 'HTTP_STATUS_404'）
    """
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        return f'ERROR_{type(e).__name__}'

def record_http_metrics(
    redis_client: Redis, 
    responses: list[Union[dict, str]],
    urls: list[str]
) -> Optional[str]:
    """记录 HTTP 请求指标到 Redis
    
    如果有多个Error则返回最后一个Error的信息

    Args:
        redis_client: Redis 客户端
        responses: fetch_data 返回结果列表

    Returns:
        错误字符串，全部成功则返回 None
    """
    today = get_current_iso_time()[:10]
    error_count = 0
    error = None

    for i, response in enumerate(responses):
        if isinstance(response, str):
            logger.warning(f'{response} {urls[i]}')
            error_count += 1
            error = response
    
    try:
        redis_client.incrby(f'metrics:http_total:{today}', len(responses))
        if error_count > 0:
            redis_client.incrby(f'metrics:http_error:{today}', error_count)
    except Exception:
        logger.warning('Failed to update HTTP metrics')

    return error

def fetch_clan_leagues(
    redis_client: Redis, 
    realm: str, 
    league: str, 
    division: str
) -> Optional[list]:
    """获取指定联赛和分段的公会排行榜数据

    Args:
        redis_client: Redis 客户端
        realm: 服务器区域
        league: 联赛等级
        division: 分段

    Returns:
        公会数据列表，每项为 [clan_id, tag, league, last_battle_timestamp]
        请求失败时返回 None。
    """
    clan_data_list = []
    url = (
        f'{CLAN_API}/api/ladder/structure/'
        f'?realm={realm}&league={league}&division={division}&limit=1000'
    )
    result = fetch_data(url)
    error = record_http_metrics(redis_client, [result], [url])
    if error:
        return None
    for temp_data in result:
        clan_data_list.append([
            temp_data['id'],
            temp_data['tag'],
            league,
            formtime_to_timestamp(temp_data['last_battle_at'])
        ])
    
    return clan_data_list

def fetch_clan_season(redis_client: Redis, clan_id: int) -> Optional[dict]:
    """从 API 获取最新的游戏版本信息

    Args:
        redis_client: Redis 客户端，用于记录请求指标
        clan_id: 工会 ID

    Returns:
        工会的当前赛季的工会战数据
        失败时返回 None
    """
    url = f'{CLAN_API}/api/clanbase/{clan_id}/claninfo/'
    result = fetch_data(url)
    error = record_http_metrics(redis_client, [result], [url])
    if error:
        return None
    return result