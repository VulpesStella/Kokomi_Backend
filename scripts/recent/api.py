"""
外部 API 请求模块

封装对 WoWS Vortex API 的异步 HTTP 调用，支持 token 鉴权、
多接口并发请求和请求指标记录。
"""

import random
import asyncio
import traceback
from redis import Redis
from httpx import AsyncClient
from typing import Optional, Union

from logger import logger
from settings import VORTEX_API
from utils import get_current_iso_time


async def fetch_data(async_client: AsyncClient, url: str):
    """发送 GET 请求并解析 JSON 响应

    Args:
        async_client: HTTP 异步客户端
        url: 请求地址

    Returns:
        成功时返回解析后的 dict，失败时返回错误标识字符串（如 'HTTP_STATUS_404'）
    """
    try:
        res = await async_client.get(url)
        request_code = res.status_code
        request_result = res.json()
        if request_code == 200:
            return request_result['data']
        # 处理用户不存在的特殊情况
        if request_code == 404:
            return {}
        return f'HTTP_STATUS_{request_code}'
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