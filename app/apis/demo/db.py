import os
import json

from app.loggers import ExceptionLogger
from app.models import PlatformModel, PlatyerModel, ClanModel
from app.core import EnvConfig
from app.response import JSONResponse
from app.utils import JsonUtils


class MySQLAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_overview():
        result = await PlatformModel.get_overview()
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def get_user_overview(account_id: int):
        result = await PlatyerModel.read_base(account_id)
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def get_clan_overview(clan_id: int):
        result = await ClanModel.read_base(clan_id)
        return result

    @ExceptionLogger.handle_program_exception_async
    async def get_recent_overview():
        result = {
            'count': 0,
            'size': 0
        }
        if EnvConfig.config.SQLITE_PATH == "default":
            SQLITE_PATH = EnvConfig.DATA_DIR / 'db'
        else:
            SQLITE_PATH = EnvConfig.config.SQLITE_PATH
        file_path = SQLITE_PATH / 'db_stats.json'
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                db_result = json.load(f)
                result['count'] = db_result['db_file_count']
                result['size'] = f"{db_result['total_size_mb']} MB"
        return JSONResponse.get_success_response(result)