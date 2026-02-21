from app.loggers import ExceptionLogger
from app.utils import GameUtils
from app.models import PlatyerModel
from app.network import ExternalAPI
from app.middlewares import RedisClient


class UserAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_base(account_id: int):
        # 获取用户的基本数据
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        else:
            ac = result['data']
        return await ExternalAPI.get_user_base(account_id, ac)
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_db_info(account_id: int):
        result = await PlatyerModel.get_user_brief(account_id)
        return result
