import httpx

from app.core import EnvConfig, api_logger
from app.response import JSONResponse
from app.loggers import ExceptionLogger
from app.schemas import GameAPIException


TIMEOUT = httpx.Timeout(
    connect = 2.0,
    read = 10.0,
    write = 3.0,
    pool = 2.0
)

class HttpClient:
    _client: httpx.AsyncClient = None

    @classmethod
    def init_client(cls) -> None:
        """初始化 HTTP 客户端"""
        if EnvConfig.SSL_CA_BUNDLE:
            api_logger.info(f'Using local certificates: {EnvConfig.SSL_CA_BUNDLE}')
            cls._client = httpx.AsyncClient(timeout=TIMEOUT, trust_env=False, verify=EnvConfig.SSL_CA_BUNDLE)
        else:
            cls._client = httpx.AsyncClient(timeout=TIMEOUT, trust_env=False)
    
    @classmethod
    async def close_client(cls) -> None:
        """关闭 HTTP 客户端"""
        if cls._client:
            await cls._client.aclose()
            cls._client = None

    @classmethod
    @ExceptionLogger.handle_network_exception_async
    async def get_user_data(cls, url):
        res = await cls._client.get(url=url)
        requset_code = res.status_code
        if requset_code == 404:
            # 用户不存在或者账号删除的情况
            return JSONResponse.success({})
        elif requset_code == 500:
            raise GameAPIException
        elif requset_code == 200:
            # 正常返回值的处理
            requset_result = res.json()
            if requset_result.get('status') == 'ok':
                data = requset_result['data']
                return JSONResponse.success(data)
            else:
                raise GameAPIException
        else:
            res.raise_for_status()  # 其他状态码

    @classmethod
    @ExceptionLogger.handle_network_exception_async
    async def get_clan_data(cls, url):
        res = await cls._client.get(url=url)
        requset_code = res.status_code
        if requset_code in [404, 503]:
            # 用户不存在或者账号删除的情况
            return JSONResponse.API_1000_Success
        elif requset_code == 500:
            raise GameAPIException
        elif requset_code == 200:
            # 正常返回值的处理
            requset_result = res.json()
            return JSONResponse.success(requset_result)
        else:
            res.raise_for_status()  # 其他状态码

    @classmethod
    @ExceptionLogger.handle_network_exception_async
    async def get_clan_search(cls, url):
        # 请求获取工会名称搜索结果
        res = await cls._client.get(url=url)
        requset_code = res.status_code
        requset_result = res.json()
        if requset_code == 200:
            data = requset_result.get('search_autocomplete_result', [])
            return JSONResponse.success(data)
        elif requset_code == 500:
            raise GameAPIException
        else:
            res.raise_for_status()  # 其他状态码

    @classmethod
    @ExceptionLogger.handle_network_exception_async
    async def get_offical_user_data(cls, url):
        res = await cls._client.get(url=url)
        requset_code = res.status_code
        requset_result = res.json()
        if requset_code == 200:
            return JSONResponse.success(requset_result)
        elif requset_code == 500:
            raise GameAPIException
        else:
            res.raise_for_status()  # 其他状态码