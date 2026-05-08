import uuid
import redis
import httpx
import traceback
import aiomysql

from .error_log import write_error_info
from app.response import JSONResponse


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
                write_error_info(
                    error_id = error_id,
                    error_type = 'ProgramError',
                    error_name = str(type(e).__name__),
                    error_args = str(args) + str(kwargs),
                    error_info = traceback.format_exc()
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
                return JSONResponse.get_error_response(3101,'HttpxConnectTimeout')
            except httpx.ReadTimeout:
                return JSONResponse.get_error_response(3102,'HttpxReadTimeout')
            except httpx.TimeoutException:
                return JSONResponse.get_error_response(3103,'HttpxTimeoutError')
            except httpx.ConnectError:
                return JSONResponse.get_error_response(3104,'HttpxConnectError')
            except httpx.ReadError:
                return JSONResponse.get_error_response(3105,'HttpxReadError')
            except httpx.HTTPStatusError:
                return JSONResponse.get_error_response(3106, 'HttpxHTTPStatusError')
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_error_info(
                    error_id = error_id,
                    error_type = 'NetworkError',
                    error_name = str(type(e).__name__),
                    error_args = str(args) + str(kwargs),
                    error_info = traceback.format_exc()
                )
                return JSONResponse.get_error_response(3100,'NetworkError',error_id)
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
                write_error_info(
                    error_id = error_id,
                    error_type = "MySQL",
                    error_name = "MySQLProgrammingError",
                    error_args = str(args) + str(kwargs),
                    error_info = f'ERROR_{e.args[0]}\n' + str(e.args[1]) + f'\n{traceback.format_exc()}'
                )
                return JSONResponse.get_error_response(3002,'MySQLProgrammingError',error_id)
            except aiomysql.OperationalError as e:
                error_id = str(uuid.uuid4())
                write_error_info(
                    error_id = error_id,
                    error_type = "MySQL",
                    error_name = "MySQLOperationalError",
                    error_args = str(args) + str(kwargs),
                    error_info = f'ERROR_{e.args[0]}\n' + str(e.args[1]) + f'\n{traceback.format_exc()}'
                )
                return JSONResponse.get_error_response(3003,'MySQLOperationalError',error_id)
            except aiomysql.IntegrityError as e:
                error_id = str(uuid.uuid4())
                write_error_info(
                    error_id = error_id,
                    error_type = "MySQL",
                    error_name = "MySQLIntegrityError",
                    error_args = str(args) + str(kwargs),
                    error_info = f'ERROR_{e.args[0]}\n' + str(e.args[1]) + f'\n{traceback.format_exc()}'
                )
                return JSONResponse.get_error_response(3004,'MySQLIntegrityError',error_id)
            except aiomysql.DatabaseError as e:
                error_id = str(uuid.uuid4())
                write_error_info(
                    error_id = error_id,
                    error_type = "MySQL",
                    error_name = "MySQLDatabaseError",
                    error_args = str(args) + str(kwargs),
                    error_info = f'ERROR_{e.args[0]}\n' + str(e.args[1]) + f'\n{traceback.format_exc()}'
                )
                return JSONResponse.get_error_response(3001,'MySQLDatabaseError',error_id)
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_error_info(
                    error_id = error_id,
                    error_type = 'ProgramError',
                    error_name = str(type(e).__name__),
                    error_info = traceback.format_exc()
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
                write_error_info(
                    error_id = error_id,
                    error_type = 'RedisError',
                    error_name = str(type(e).__name__),
                    error_args = str(args) + str(kwargs),
                    error_info = f'\n{traceback.format_exc()}'
                )
                return JSONResponse.get_error_response(3005,'RedisError',error_id)
            except Exception as e:
                error_id = str(uuid.uuid4())
                write_error_info(
                    error_id = error_id,
                    error_type = 'ProgramError',
                    error_name = str(type(e).__name__),
                    error_args = str(args) + str(kwargs),
                    error_info = traceback.format_exc()
                )
                return JSONResponse.get_error_response(3000,'ProgramError',error_id)
        return wrapper
    