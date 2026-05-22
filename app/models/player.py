from app.core import EnvConfig
from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.utils import TimeUtils


class DemoPlayerModel:
    @ExceptionLogger.handle_database_exception_async
    async def read_base(account_id: int):
        '''
        从数据库中获取用户的基本数据
        '''
        async with MySQLManager.read_only_cursor() as cur:
            data = {
                'region': EnvConfig.REGION,
                'user_id': account_id,
                'username': None,
                'is_enabled': False,
                'is_public': False
            }
            # 读user_base库
            sql = """
                SELECT
                    username
                FROM T_user_base
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if not row:
                return JSONResponse.API_2016_UserNotInDB
            data['username'] = row[0]
            # 读user_stats库
            sql = """
                SELECT
                    is_enabled,
                    is_public,
                    activity_level,
                    total_battles, 
                    UNIX_TIMESTAMP(next_refresh_at)
                FROM T_user_stats
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['is_enabled'] = row[0]
                data['is_public'] = row[1]
            if not data['is_enabled'] or not data['is_public']:
                return JSONResponse.get_success_response(data)
            data['activity_level'] = row[2]
            data['total_battles'] = row[3]
            data['next_refresh_at'] = TimeUtils.fromtimestamp(row[4])
            # 读user_config库
            sql = """
                SELECT
                    user_level,
                    storage_limit,
                    query_count,
                    UNIX_TIMESTAMP(last_query_at)
                FROM T_user_config
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['user_level'] = row[0]
                data['storage_limit'] = row[1]
                data['query_count'] = row[2]
                data['last_query_time'] = TimeUtils.fromtimestamp(row[3])
            # 读user_clan库
            sql = """
                SELECT
                    clan_id
                FROM T_user_clan
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            row = await cur.fetchone()
            if row:
                data['clan_id'] = row[0]
            return JSONResponse.get_success_response(data)

class PlayerModel:
    @ExceptionLogger.handle_database_exception_async
    async def record_query(account_id: int):
        """记录一次用户查询"""
        async with MySQLManager.auto_transaction_cursor() as cur:
            sql = """
                UPDATE T_user_config
                SET
                    query_count = query_count + 1,
                    last_query_at = NOW()
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            return JSONResponse.API_1000_Success
        
    @ExceptionLogger.handle_database_exception_async
    async def get_user_name_and_clan(account_id: int):
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT 
                    account_id,
                    username,
                    register_time,
                    insignias,
                    clan_id,
                    clan_tag,
                    league
                FROM V_user_basic_with_clan
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            data = await cur.fetchone()
            return JSONResponse.get_success_response(data)