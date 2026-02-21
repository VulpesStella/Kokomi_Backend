import os
import json

from app.loggers import ExceptionLogger
from app.models import PlatformModel
from app.core import EnvConfig
from app.response import JSONResponse
from app.utils import JsonUtils


class MySQLAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_innodb_trx():
        result = await PlatformModel.get_innodb_trx()
        return result

    @ExceptionLogger.handle_program_exception_async
    async def get_innodb_processlist():
        result = await PlatformModel.get_innodb_processlist()
        return result

    @ExceptionLogger.handle_program_exception_async
    async def get_basic_user_overview():
        result = await PlatformModel.get_basic_user_overview()
        return result

    @ExceptionLogger.handle_program_exception_async
    async def get_basic_clan_overview():
        result = await PlatformModel.get_basic_clan_overview()
        return result
    
    @ExceptionLogger.handle_program_exception_async
    async def get_db_size():
        result = {
            'mysql': 0,
            'ranking': 0,
            'recent': 0
        }
        db_result = await PlatformModel.database_size()
        if db_result['code'] != 1000:
            return db_result
        result['mysql'] = f"{db_result['data']} MB"
        file_name_list = ['leaderboard_user.db', 'leaderboard_ship.db']
        for file_name in file_name_list:
            file_path = EnvConfig.DATA_DIR / 'cache' / file_name
            if file_path.exists():
                result['ranking'] += round(os.path.getsize(file_path) / (1024 * 1024), 2)
            result['ranking'] = f"{result['ranking']} MB"
        if EnvConfig.config.SQLITE_PATH == "default":
            SQLITE_PATH = EnvConfig.DATA_DIR / 'db'
        else:
            SQLITE_PATH = EnvConfig.config.SQLITE_PATH
        file_path = SQLITE_PATH / 'db_stats.json'
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                db_result = json.load(f)
                result['recent'] = f"{db_result['total_size_mb']} MB"
        return JSONResponse.get_success_response(result)