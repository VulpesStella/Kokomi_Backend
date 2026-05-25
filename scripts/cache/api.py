import random
import requests
import traceback
from redis import Redis
from typing import Optional, Union

from logger import logger
from utils import get_current_iso_time
from settings import VORTEX_API


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
            data = resp.json()
            if data.get('status') == 'ok':
                return data.get('data', {})
            else:
                return "Game_API_Failed"
        elif resp.status_code == 404:
            return {}
        return f'HTTP_STATUS_{resp.status_code}'
    except Exception as e:
        return f'ERROR_{type(e).__name__}'

def record_http_metrics(
    redis_client: Redis, 
    responses: list[Union[dict, str]],
    urls: list[str]
) -> Optional[str]:
    """记录 HTTP 请求指标到 Redis

    如果有多个 Error 则返回最后一个 Error 的信息

    Args:
        redis_client: Redis 客户端
        responses: fetch_data 返回结果列表
        urls: 对应请求的 URL 列表，用于日志输出

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

def fetch_user_pvp_data(
    redis_client: Redis,
    account_id: int
) -> Optional[list[Union[dict, str]]]:
    """获取用户的三个接口数据（基本信息、船只统计、PvP 详细）

    Args:
        redis_client: Redis 客户端（用于指标记录和 token 获取）
        account_id: 用户 ID

    Returns:
        成功时返回 {}
        失败时返回 None
    """
    try:
        redis_key = f"token:ac:{account_id}"
        ac = redis_client.get(redis_key)
        base_url = random.choice(VORTEX_API)

        url = f'{base_url}/api/accounts/{account_id}/ships/pvp/' + (f'?ac={ac}' if ac else '')

        result = fetch_data(url)
        error = record_http_metrics(redis_client, [result], [url])
        if error:
            return

        return result
    except Exception:
        logger.error(traceback.format_exc())