import shutil

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse
from app.models import RecentModel
from app.middlewares import RedisClient


RECENT_LEVEL_OFF = 0
RECENT_LEVEL_STANDARD = 1
RECENT_LEVEL_PLUS = 2

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
        ac = result['data']
        result = await ExternalAPI.get_user_header(account_id, ac)
        if result['code'] != 1000:
            return result
        return JSONResponse.get_success_response(result)
    
    @ExceptionLogger.handle_program_exception_async
    async def set_recent(account_id: int, level: str):
        '''启用用户recent功能'''
        level_map = {
            "standard": RECENT_LEVEL_STANDARD,
            "plus": RECENT_LEVEL_PLUS
        }
        target_level = level_map.get(level)
        if target_level is None:
            return JSONResponse.API_1000_Success
        
        return await RecentModel.test_set_recent_level(account_id, target_level)

    @ExceptionLogger.handle_program_exception_async
    async def del_recent(account_id: int, level: str):
        '''降低/关闭用户recent功能'''
        level_map = {
            "off": RECENT_LEVEL_OFF,
            "standard": RECENT_LEVEL_STANDARD
        }
        target_level = level_map.get(level)
        if target_level is None:
            return JSONResponse.API_1000_Success
        
        result = await RecentModel.test_reduce_recent_level(account_id, target_level)
        if result['code'] != 1000:
            return result
        
        # 关闭recent功能时，删除用户的recent数据库文件
        if level == "off":
            user_db_file = EnvConfig.SQLITE_DIR / f'{account_id}.db'
            if user_db_file.exists():
                shutil.move(user_db_file, EnvConfig.DATA_DIR / f'trash/recent_{account_id}.db')
        
        return JSONResponse.API_1000_Success