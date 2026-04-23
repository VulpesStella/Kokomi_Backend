from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse
from app.models import PlatyerModel
from app.middlewares import RedisClient


class TestAPI:
    @ExceptionLogger.handle_program_exception_async
    async def test_error_log():
        raise NotImplementedError
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_base(account_id: int):
        # 获取用户的基本数据
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        else:
            ac = result['data']
        return await ExternalAPI.get_user_base(account_id, ac)
    
    @staticmethod
    @ExceptionLogger.handle_program_exception_async
    async def get_user_header(account_id: int):
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        if result['data']:
            ac = result['data']
        else:
            ac = None
        # 先读数据库，读不到数据再请求
        result = await PlatyerModel.get_user_name(account_id)
        if result['code'] != 1000:
            return result
        if result['data'] is None:
            # 数据库中无用户数据，进行网络请求获取数据
            result = await ExternalAPI.get_user_brief(account_id, ac)
            if result['code'] != 1000:
                return result
        data = {
            'type': 'clan_battle',
            'basic': result['data'],
            'statistics': {}
        }

        return JSONResponse.get_success_response(data)
