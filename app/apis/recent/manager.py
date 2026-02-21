from app.loggers import ExceptionLogger
from app.utils import TimeUtils
from app.models import RecentModel
from app.network import ExternalAPI
from app.middlewares import RedisClient
from app.response import JSONResponse


class RecentManagerAPI:
    @ExceptionLogger.handle_program_exception_async
    async def enable_recent(account_id: int):
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        ac = result['data']
        result = await ExternalAPI.get_user_base(account_id, ac)
        if result['code'] != 1000:
            return result
        # recent功能需要: 1.用户存在且公开战绩 2.近一年内活跃
        lbt = result['data']['last_battle_time']
        now_timestamp = TimeUtils.timestamp()
        if lbt is None or now_timestamp - lbt > 360*24*60*60:
            return JSONResponse.API_2016_AccountNotEligible
        else:
            result = await RecentModel.recent_enable(account_id)
            return result
        
    @ExceptionLogger.handle_program_exception_async
    async def delete_recent(account_id: int):
        result = await RecentModel.recent_close(account_id)
        return result
        
    @ExceptionLogger.handle_program_exception_async
    async def enable_recent_pro(account_id: int):
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        ac = result['data']
        result = await ExternalAPI.get_user_base(account_id, ac)
        if result['code'] != 1000:
            return result
        # recentpro功能需要: 1.用户存在且公开战绩 2.近三个月活跃
        lbt = result['data']['last_battle_time']
        now_timestamp = TimeUtils.timestamp()
        if lbt is None or now_timestamp - lbt > 90*24*60*60:
            return JSONResponse.API_2016_AccountNotEligible
        else:
            result = await RecentModel.daily_enable(account_id)
            return result
        
    @ExceptionLogger.handle_program_exception_async
    async def delete_recent_pro(account_id: int):
        result = await RecentModel.daily_close(account_id)
        return result