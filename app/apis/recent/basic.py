import sqlite3

from app.core import EnvConfig
from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.middlewares import RedisClient
from app.response import JSONResponse
from app.models import PlayerModel
from app.utils import TimeUtils

from .summary import RecentSummary
from .calculate import CalculateRecent

class RecentAPI:
    @ExceptionLogger.handle_program_exception_async
    async def summary(account_id: int):
        error, user_config = JSONResponse.extract_data_strict(
            response=await PlayerModel.get_user_config(account_id)
        ) 
        if error:
            return user_config
        
        user_level = {
            1: "Standard",
            2: "Plus"
        }.get(user_config[0])
        storage_limit = user_config[1]
        if user_level is None:
            return JSONResponse.API_2023_UserRecentDisabled
        
        db_path = EnvConfig.SQLITE_DIR / f'{account_id}.db'
        if not db_path.exists():
            return JSONResponse.API_2020_DataIntegrityError
        
        total_dates = 0
        total_rows = 0
        total_error = 0
        
        file_size_kb = db_path.stat().st_size // 1024
        if file_size_kb > 1024:
            file_size_mb = str(file_size_kb // 1024)
        else:
            file_size_mb = '< 1'

        current_timestamp = TimeUtils.timestamp()

        with sqlite3.connect(db_path) as conn:
            try:
                cursor = conn.cursor()
                start_date = RecentSummary.read_start_date(cursor)
                total_rows = RecentSummary.read_total_rows(cursor)
                summary = RecentSummary.read_daily_summary(cursor, current_timestamp, start_date)
                if summary == {}:
                    return JSONResponse.API_2020_DataIntegrityError
            finally:
                cursor.close()

        hot_map = []
        values = list(summary.values())
        total_dates = len(values) - 1
        for i in range(total_dates):
            if values[i] is None:
                total_error += 1
                hot_map.append(None)
            elif values[i] == -1:
                hot_map.append(-1)
            else:
                if values[i+1] is None:
                    total_error += 1
                    hot_map.append(None)
                if values[i+1] >= 0:
                    diff_battles = values[i] - values[i+1]
                    hot_map.append(max(0, diff_battles))
                else:
                    hot_map.append(0)

        result = {
            'basic': {
                'region': EnvConfig.REGION,
                'user_id': account_id
            },
            'overall': {
                'user_level': user_level,
                'storage_limit': str(storage_limit),
                'total_dates': str(total_dates),
                'total_rows': str(total_rows),
                'total_error': str(total_error),
                'file_size': file_size_mb
            },
            'hot_map': hot_map
        }

        return JSONResponse.get_success_response(result)

    @ExceptionLogger.handle_program_exception_async
    async def ranked(account_id: int, start_date: int, end_date: int):
        db_path = EnvConfig.SQLITE_DIR / f'{account_id}.db'
        if not db_path.exists():
            return JSONResponse.API_2023_UserRecentDisabled
        
        result = CalculateRecent.calc_ranked_recent(account_id, start_date, end_date)

        return JSONResponse.get_success_response(result)