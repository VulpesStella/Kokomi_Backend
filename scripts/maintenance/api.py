import random
import requests
import traceback
from redis import Redis
from typing import Optional, Union

from logger import logger
from settings import VORTEX_API
from utils import get_current_iso_time


def fetch_data(url):
    """发送 GraphQL 查询到指定 URL，获取游戏版本数据

    Args:
        url: 完整的 API 地址

    Returns:
        成功时返回 JSON 解析后的字典
    """
    try:
        body = [{"query":"query Version {\n  version\n}"}]
        resp = requests.post(url,json=body,timeout=5)
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

def fetch_latest_version(redis_client: Redis) -> Optional[dict]:
    """从 API 获取最新的游戏版本信息

    Args:
        redis_client: Redis 客户端，用于记录请求指标

    Returns:
        包含 'short' 和 'full' 键的 Dict
        失败时返回 None
    """
    try:
        base_url = random.choice(VORTEX_API)
        url = f'{base_url}/api/v2/graphql/glossary/version/'
        result = fetch_data(url)
        error = record_http_metrics(redis_client, [result], [url])
        if error:
            return
        
        version = result[0]['data']['version']
        return {
            'short': ".".join(version.split(".")[:2]),
            'full': version
        }
    except Exception:
        logger.error(traceback.format_exc())
