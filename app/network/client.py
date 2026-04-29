import httpx

from app.core import api_logger

from .response import JSONResponse
from .exception import handle_network_exception_async


TIMEOUT = httpx.Timeout(
    connect = 2.0,
    read = 10.0,
    write = 3.0,
    pool = 2.0
)
# 关闭代理，避免请求外部API时被本地环境变量干扰
async_client = httpx.AsyncClient(timeout=TIMEOUT, trust_env=False)

class HttpClient:
    """负责和外部API交互"""
    @handle_network_exception_async
    async def get_user_search(url):
        # 请求获取工会名称搜索结果
        res = await async_client.get(url=url)
        requset_code = res.status_code
        requset_result: dict = res.json()
        if requset_code == 200:
            data = requset_result.get('data', [])
            return JSONResponse.get_success_response(data)
        if requset_code in [400, 500, 503]:
            # 用户搜索接口还可能的返回值，主要是国服相关接口不支持模糊搜索导致的
            return JSONResponse.get_success_response([])
        else:
            api_logger.warning(f"Code{requset_code} {url}")
            res.raise_for_status()  # 其他状态码

    @handle_network_exception_async
    async def get_clan_search(url):
        # 请求获取工会名称搜索结果
        res = await async_client.get(url=url)
        requset_code = res.status_code
        requset_result: dict = res.json()
        if requset_code == 200:
            data = requset_result.get('search_autocomplete_result', [])
            return JSONResponse.get_success_response(data)
        else:
            api_logger.warning(f"Code{requset_code} {url}")
            res.raise_for_status()  # 其他状态码

    @handle_network_exception_async
    async def get_user_data(url):
        res = await async_client.get(url=url)
        requset_code = res.status_code
        requset_result = res.json()
        if requset_code == 404:
            # 用户不存在或者账号删除的情况
            return JSONResponse.API_1000_Success
        elif requset_code == 200:
            # 正常返回值的处理
            data = requset_result['data']
            return JSONResponse.get_success_response(data)
        else:
            api_logger.warning(f"Code{requset_code} {url}")
            res.raise_for_status()  # 其他状态码

    @handle_network_exception_async
    async def get_offical_user_data(url):
        res = await async_client.get(url=url)
        requset_code = res.status_code
        requset_result = res.json()
        if requset_code == 200:
            return JSONResponse.get_success_response(requset_result)
        else:
            api_logger.warning(f"Code{requset_code} {url}")
            res.raise_for_status()  # 其他状态码