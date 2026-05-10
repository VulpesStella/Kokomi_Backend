from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse


class PlatformModel:
    @ExceptionLogger.handle_database_exception_async
    async def reset_tracking_time(tracking_key: str, tracking_type: str):
        """将指定追踪键和类型的记录置为 NULL，触发服务立即刷新"""
        async with MySQLManager.auto_transaction_cursor() as cur:
            sql = """
                UPDATE T_tracking_meta 
                SET 
                    tracking_value = NULL 
                WHERE tracking_key = %s 
                  AND tracking_type = %s;
            """
            await cur.execute(sql, [tracking_key, tracking_type])
            
            return JSONResponse.API_1000_Success