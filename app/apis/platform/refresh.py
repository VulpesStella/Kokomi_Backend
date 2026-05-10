from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.response import JSONResponse, ResponseDict
from app.middlewares import RedisClient
from app.models import UserStatsSyncer, UserClanSyncer



class RefreshAPI:
    @ExceptionLogger.handle_program_exception_async
    async def refresh_user(account_id: int) -> ResponseDict:
        # 从 Redis 中获取用户的 access_token
        redis_key = f"token:ac:{account_id}"
        response = await RedisClient.get_token(redis_key)
        error, access_token = JSONResponse.extract_data_strict(response)
        if error:
            return access_token
        
        response = await ExternalAPI.get_user_basic(account_id, True, access_token)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        
        user_data = result[0]
        user_clan = result[1]

        # 用户不存在情况下不执行后续数据库刷新步骤
        user_info = user_data.get(str(account_id)) if user_data else None
        if (
            user_info is None or 
            (
                'hidden_profile' not in user_info and 
                'statistics' not in user_info
            )
        ):
            return JSONResponse.API_2011_UserNotExist

        response = await UserStatsSyncer.refresh(account_id, user_data)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        response = await UserClanSyncer.refresh(account_id, user_clan)
        error, result = JSONResponse.extract_data_strict(response)
        if error:
            return result
        
        return JSONResponse.API_1000_Success
        