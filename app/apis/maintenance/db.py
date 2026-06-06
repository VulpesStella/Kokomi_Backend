from app.loggers import ExceptionLogger
from app.models import PlatformModel
from app.response import JSONResponse

class MaintenanceAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_database_meta():
        error, game_version = JSONResponse.extract_data_strict(
            response=await PlatformModel.read_latest_version()
        )
        if error:
            return game_version
        
        error, table_meta = JSONResponse.extract_data_strict(
            response=await PlatformModel.read_table_meta()
        )
        if error:
            return table_meta
        
        error, database_meta = JSONResponse.extract_data_strict(
            response=await PlatformModel.read_database_meta()
        )
        if error:
            return database_meta
        
        error, user_activity = JSONResponse.extract_data_strict(
            response=await PlatformModel.read_user_activity_distribution()
        )
        if error:
            return user_activity
        
        user_activity_distribution = {}
        for user in user_activity:
            user_activity_distribution[str(user[0])] = user[1]

        error, clan_activity = JSONResponse.extract_data_strict(
            response=await PlatformModel.read_clan_activity_distribution()
        )
        if error:
            return clan_activity
        
        clan_activity_distribution = {}
        for clan in clan_activity:
            clan_activity_distribution[str(clan[0])] = clan[1]
        
        result = {
            'version': game_version,
            'user': {
                'total': table_meta.get('base_users', 0),
                'recent_lv1': table_meta.get('recent_lv1', 0),
                'recent_lv2': table_meta.get('recent_lv2', 0),
                'activity': user_activity_distribution
            },
            'clan': {
                'total': table_meta.get('base_clans', 0),
                'activity': clan_activity_distribution
            },
            'cache': {
                'users': table_meta.get('total_users', 0),
                'ships': table_meta.get('ship_entries', 0),
                'battles': table_meta.get('total_battles', 0),
                'rows': table_meta.get('leaderboard_rows', 0)
            },
            'mysql': {
                'tables': database_meta.get('mysql_tables', 0),
                'rows': database_meta.get('mysql_rows', 0),
                'size_kb': database_meta.get('mysql_size_kb', 0)
            },
            'sqlite': {
                'files': database_meta.get('sqlite_files', 0),
                'size_kb': database_meta.get('sqlite_size_kb', 0)
            }
        }

        return JSONResponse.get_success_response(result)