from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse
from app.constants import Limits


class DemoRecentModel:
    @ExceptionLogger.handle_database_exception_async
    async def set_recent_level(account_id: int, target_level: int):
        '''[DEMO] 设置用户recent功能级别

        只允许向上升级，数据库level低于目标level时才会修改
        '''
        async with MySQLManager.auto_transaction_cursor() as cur:
            sql = """
                SELECT 
                    user_level, 
                    storage_limit 
                FROM T_user_config 
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            data = await cur.fetchone()
            if data is None:
                return JSONResponse.API_1000_Success
            
            current_level = data[0]
            # 只允许向上升级
            if current_level < target_level:
                storage_level = Limits.DefaultRecentLimit if target_level == 1 else Limits.DefaultRecentProLimit
                sql = """
                    UPDATE T_user_config 
                    SET 
                        user_level = %s, 
                        storage_limit = %s
                    WHERE account_id = %s;
                """
                await cur.execute(sql, [target_level, storage_level, account_id])
            
            return JSONResponse.API_1000_Success

    @ExceptionLogger.handle_database_exception_async
    async def reduce_recent_level(account_id: int, target_level: int):
        '''[DEMO] 降低用户recent功能级别
        
        只允许向下降级，高级可降到标准或无，标准可降到无
        '''
        async with MySQLManager.auto_transaction_cursor() as cur:
            sql = """
                SELECT 
                    user_level, 
                    storage_limit 
                FROM T_user_config 
                WHERE account_id = %s;
            """
            await cur.execute(sql, [account_id])
            data = await cur.fetchone()
            if data is None:
                return JSONResponse.API_1000_Success
            
            current_level = data[0]
            # 只允许向下降级：2→1/0, 1→0
            if current_level > target_level and not (current_level == 1 and target_level != 0):
                # 处理降级的storage_limit
                new_limit = Limits.DefaultRecentLimit if target_level == 1 else 0
                
                sql = """
                    UPDATE T_user_config 
                    SET 
                        user_level = %s, 
                        storage_limit = %s
                    WHERE account_id = %s;
                """
                await cur.execute(sql, [target_level, new_limit, account_id])
            
            return JSONResponse.API_1000_Success


class RecentModel:
    ...