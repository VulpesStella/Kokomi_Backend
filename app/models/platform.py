from app.core import EnvConfig
from app.database import MySQLManager
from app.loggers import ExceptionLogger
from app.response import JSONResponse


class PlatformModel:
    @ExceptionLogger.handle_database_exception_async
    async def read_database_stats():
        config = EnvConfig.get_config()
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT 
                    COUNT(*),
                    SUM(data_length + index_length) / 1024 / 1024,
                    SUM(table_rows)
                FROM information_schema.tables
                WHERE table_schema = %s
                GROUP BY table_schema;
            """
            await cur.execute(sql, [config.MYSQL.db])
            row = await cur.fetchone()
            data = {
                'table_count': row[0],
                'total_size': round(row[1], 2),
                'total_rows': row[2]
            }
            return JSONResponse.get_success_response(data)
        
    @ExceptionLogger.handle_database_exception_async
    async def read_latest_version():
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT 
                    short_name 
                FROM T_game_version 
                WHERE is_latest = TRUE 
                LIMIT 1;
            """
            await cur.execute(sql)
            data = await cur.fetchone()

            return JSONResponse.get_success_response(data[0] if data else None)
        
    @ExceptionLogger.handle_database_exception_async
    async def read_table_meta():
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT 
                    metric_key, 
                    metric_value 
                FROM T_table_meta;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            data = {}
            for row in rows:
                data[row[0]] = row[1]
            return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_database_exception_async
    async def read_archive_stats(table_name: str):
        """读取归档表的每日行数变化

        Args:
            table_name: ARCH_user_base 或 ARCH_clan_base

        Returns:
            success → {code: 1000, data: [(stat_date, row_count), ...]}
            failure  → {code: error_code, ...}
        """
        async with MySQLManager.read_only_cursor() as cur:
            sql = f"""
                SELECT
                    stat_date,
                    row_count
                FROM {table_name}
                ORDER BY stat_date ASC;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            data = [(row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]), row[1]) for row in rows]
            return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_database_exception_async
    async def read_user_level_distribution():
        """读取用户等级分布 (0-2)

        Returns:
            success → {code: 1000, data: [(user_level, count), ...]}
        """
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT
                    user_level,
                    COUNT(*) AS cnt
                FROM T_user_config
                GROUP BY user_level
                ORDER BY user_level;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            data = [(row[0], row[1]) for row in rows]
            return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_database_exception_async
    async def read_user_refresh_stats():
        """读取用户刷新计划分布

        Returns:
            success → {code: 1000, data: [(status, user_count), ...]}
        """
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT
                    status,
                    user_count
                FROM T_user_refresh_stats
                ORDER BY
                    CASE status
                        WHEN 'overdue' THEN 1
                        WHEN 'today' THEN 2
                        WHEN 'within_week' THEN 3
                        WHEN 'within_month' THEN 4
                        WHEN 'within_quarter' THEN 5
                    END;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            data = [(row[0], row[1]) for row in rows]
            return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_database_exception_async
    async def read_user_activity_distribution():
        """读取用户活跃度分布 (0-9) 从 V_user_activity_distribution

        Returns:
            success → {code: 1000, data: [(activity_level, cnt), ...]}
        """
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT
                    activity_level,
                    cnt
                FROM V_user_activity_distribution
                ORDER BY activity_level;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            data = [(row[0], row[1]) for row in rows]
            return JSONResponse.get_success_response(data)

    @ExceptionLogger.handle_database_exception_async
    async def read_user_refresh_hourly_stats():
        """读取未来24h刷新计划每小时分布

        Returns:
            success → {code: 1000, data: [(planned_hour, planned_count), ...]}
        """
        async with MySQLManager.read_only_cursor() as cur:
            sql = """
                SELECT
                    planned_hour,
                    planned_count
                FROM T_user_refresh_hourly_stats
                ORDER BY planned_hour;
            """
            await cur.execute(sql)
            rows = await cur.fetchall()
            data = [(row[0], row[1]) for row in rows]
            return JSONResponse.get_success_response(data)

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