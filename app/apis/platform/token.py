from app.loggers import ExceptionLogger
from app.middlewares import RedisClient
from app.utils import TimeUtils
from app.network import ExternalAPI
from app.response import JSONResponse

class TokenAPI:
    @ExceptionLogger.handle_program_exception_async
    async def set_ac(account_id: int, access_token: str):
        """
        设置ac
        """
        result = await ExternalAPI.varify_ac(account_id,access_token)
        if result['code'] != 1000:
            return result
        if result['data'] == False:
            return JSONResponse.API_2005_InvalidAccessToken
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.set(redis_key,access_token)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def set_auth(account_id: int, access_token: str, expires_at: int):
        redis_key = f"token:auth:{account_id}"
        vaildity = expires_at-TimeUtils.timestamp() - 60
        result = await RedisClient.set(redis_key,access_token,vaildity)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def del_auth(account_id: int):
        """
        删除ac
        """
        redis_key = f"token:auth:{account_id}"
        result = await RedisClient.drop(redis_key)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def del_ac(account_id: int):
        """
        删除ac
        """
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.drop(redis_key)
        return result

