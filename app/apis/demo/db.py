from app.loggers import ExceptionLogger
from app.response import JSONResponse, ResponseDict
from app.models import (
    DemoPlayerModel, 
    DemoClanModel, 
    PlatformModel
)


# 映射：tracking_key -> tracking_type
TRACKING_KEY_TYPE_MAP = {
    'ship_users': 'archive_time',
    'ship_battles': 'archive_time',
    'ship_stats': 'update_time',
    'maintenance': 'update_time',
    'clan_season': 'refresh_time',
}

class MySQLAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_user_overview(account_id: int) -> ResponseDict:
        result = await DemoPlayerModel.read_base(account_id)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_overview(clan_id: int) -> ResponseDict:
        result = await DemoClanModel.read_base(clan_id)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def reset_tracking_time(tracking_key: str) -> ResponseDict:
        tracking_type = TRACKING_KEY_TYPE_MAP.get(tracking_key)
        if not tracking_type:
            return JSONResponse.API_1000_Success
        result = await PlatformModel.reset_tracking_time(tracking_key, tracking_type)
        return result