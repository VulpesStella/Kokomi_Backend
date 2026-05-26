import requests
import traceback
from redis import Redis
from typing import Optional, Union

from logger import logger
from utils import get_current_iso_time
from exception import write_exception
from settings import CLAN_API


def fetch_data(url: str) -> Union[dict, str]:
    """发送 GET 请求并解析 JSON 响应

    Args:
        url: 请求地址

    Returns:
        成功时返回解析后的 dict，失败时返回错误标识字符串
    """
    try:
        resp = requests.get(url, timeout=5)

        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'ok':
                return data.get('items', [])
            else:
                return "Game_API_Error"
        
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
    error_count = 0
    error = None

    today = get_current_iso_time()[:10]

    # 检查所有的返回数据
    for i, response in enumerate(responses):
        if isinstance(response, str):
            logger.warning(f'{response} {urls[i]}')
            error_count += 1
            error = response
    
    # 记录游戏 API 调用的统计数据
    try:
        redis_client.incrby(f'metrics:total:http', len(urls))
        redis_client.incrby(f'metrics:http_total:{today}', len(urls))

        if error_count > 0:
            redis_client.incrby(f'metrics:http_error:{today}', error_count)
    except Exception:
        logger.warning('Failed to record HTTP metrics')

    return error

def fetch_clan_members(redis_client: Redis, clan_id: int) -> Optional[dict]:
    """获取指定公会的当前赛季详情数据

    Args:
        redis_client: Redis 客户端，用于记录请求指标
        clan_id: 公会 ID

    Returns:
        公会内玩家信息列表，失败时返回 None
    """
    try:
        url = f'{CLAN_API}/api/members/{clan_id}/'
        response = fetch_data(url)

        error = record_http_metrics(redis_client, [response], [url])
        if error:
            return

        return response
    except Exception as e:
        error_name = type(e).__name__
        logger.error(f"Fetch user data failed: {error_name}")
        write_exception(
            error_type="NetworkError",
            error_name=error_name,
            error_info=traceback.format_exc()
        )