import uuid
import redis
import httpx
import traceback
import aiomysql

from app.schemas import GameAPIException
from app.response import JSONResponse
from .error_log import write_exception


class ExceptionLogger:
    @staticmethod
    def handle_program_exception_async(func):
        "负责异步程序异常信息的捕获"
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = "ProgramError",
                    error_name = type(e).__name__,
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3000,'ProgramError',error_id)
        return wrapper
    
    @staticmethod
    def handle_network_exception_async(func):
        "负责异步网络请求 httpx 的异常捕获"
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except httpx.ConnectTimeout:
                return JSONResponse.get_api_failed_response('HttpxConnectTimeout')
            except httpx.ReadTimeout:
                return JSONResponse.get_api_failed_response('HttpxReadTimeout')
            except httpx.TimeoutException:
                return JSONResponse.get_api_failed_response('HttpxTimeoutError')
            except httpx.ConnectError:
                return JSONResponse.get_api_failed_response('HttpxConnectError')
            except httpx.ReadError:
                return JSONResponse.get_api_failed_response('HttpxReadError')
            except httpx.HTTPStatusError:
                return JSONResponse.get_api_failed_response('HttpxHTTPStatusError')
            except GameAPIException:
                return JSONResponse.get_api_failed_response('GameAPIException')
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = 'ProgramError',
                    error_name = type(e).__name__,
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3000,'ProgramError',error_id)
        return wrapper
        
    @staticmethod
    def handle_database_exception_async(func):
        "负责异步数据库 aiomysql 的异常捕获"
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except aiomysql.ProgrammingError as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = "DatabaseError",
                    error_name = "MySQLProgrammingError",
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3002,'MySQLProgrammingError',error_id)
            except aiomysql.OperationalError as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = "DatabaseError",
                    error_name = "MySQLOperationalError",
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3003,'MySQLOperationalError',error_id)
            except aiomysql.IntegrityError as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = "DatabaseError",
                    error_name = "MySQLIntegrityError",
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3004,'MySQLIntegrityError',error_id)
            except aiomysql.DatabaseError as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = "DatabaseError",
                    error_name = "MySQLDatabaseError",
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3001,'MySQLDatabaseError',error_id)
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = 'ProgramError',
                    error_name = type(e).__name__,
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3000,'ProgramError',error_id)
        return wrapper
    
    @staticmethod
    def handle_cache_exception_async(func):
        "负责缓存 Redis 的异常捕获"
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except redis.RedisError as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = 'RedisError',
                    error_name = type(e).__name__,
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3005,'RedisError',error_id)
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_exception(
                    error_type = 'ProgramError',
                    error_name = type(e).__name__,
                    error_info = traceback.format_exc(),
                    error_id=error_id
                )
                return JSONResponse.get_error_response(3000,'ProgramError',error_id)
        return wrapper
    