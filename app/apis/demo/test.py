import shutil

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse
from app.models import RecentModel
from app.middlewares import RedisClient


class TestAPI:
    @ExceptionLogger.handle_program_exception_async
    async def test_error_log():
        raise NotImplementedError
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_basic(account_id: int):
        # 获取用户的基本数据
        redis_key = f"token:ac:{account_id}"
        result = await RedisClient.get(redis_key)
        if result['code'] != 1000:
            return result
        else:
            ac = result['data']
        return await ExternalAPI.test_get_user_basic(account_id, ac)
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_clan(account_id: int):
        # 获取用户的工会数据
        return await ExternalAPI.test_get_user_clan(account_id)

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
        result = await ExternalAPI.get_user_header(account_id, ac)
        if result['code'] != 1000:
            return result
        return JSONResponse.get_success_response(result)
    
    @ExceptionLogger.handle_program_exception_async
    async def set_recent(account_id: int):
        return await RecentModel.test_recent_enable(account_id)
    
    @ExceptionLogger.handle_program_exception_async
    async def del_recent(account_id: int):
        result = await RecentModel.test_recent_close(account_id)
        if result['code'] != 1000:
            return result
        user_db_file = EnvConfig.SQLITE_DIR / f'{account_id}.db'
        if user_db_file.exists():
            shutil.move(user_db_file, EnvConfig.DATA_DIR / f'trash/recent_{account_id}.db')
        return JSONResponse.API_1000_Success
    
    @ExceptionLogger.handle_program_exception_async
    async def set_recents(account_id: int):
        return await RecentModel.test_daily_enable(account_id)
    
    @ExceptionLogger.handle_program_exception_async
    async def del_recents(account_id: int):
        result = await RecentModel.test_daily_close(account_id)
        if result['code'] != 1000:
            return result
        user_db_file = EnvConfig.SQLITE_DIR / f'{account_id}.db'
        if user_db_file.exists():
            shutil.move(user_db_file, EnvConfig.DATA_DIR / f'trash/recent_{account_id}.db')
        return JSONResponse.API_1000_Success