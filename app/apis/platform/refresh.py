from typing import Dict, Any
from dataclasses import dataclass, field

from app.loggers import ExceptionLogger
from app.network import ExternalAPI
from app.core import EnvConfig
from app.response import JSONResponse, ResponseDict
from app.middlewares import RedisClient
from app.models import UserStatsSyncer, UserClanSyncer, PlayerModel


@dataclass
class UserRefreshResponse:
    """排行榜响应数据结构"""
    basic: Dict[str, Any] = field(default_factory=dict)
    credits: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'basic': self.basic,
            'credits': self.credits
        }

class RefreshAPI:
    @ExceptionLogger.handle_program_exception_async
    async def refresh_user(account_id: int) -> ResponseDict:
        if EnvConfig.DEV_MODE:
            return JSONResponse.API_Maintenance
        
        # 从 Redis 中获取用户的 access_token
        redis_key = f"token:ac:{account_id}"
        error, access_token = JSONResponse.extract_data(
            response=await RedisClient.get_token(redis_key)
        )
        if error:
            return access_token
        
        error, result = JSONResponse.extract_data(
            response=await ExternalAPI.get_user_refresh(account_id, access_token)
        )
        if error:
            return result
        
        user_data = result[0]
        user_clan = result[1]

        # 用户不存在情况下不执行后续数据库刷新步骤
        user_info = user_data.get(str(account_id))

        if user_info is None:
            return JSONResponse.API_UserNotExist
        
        if 'hidden_profile' in user_info:
            return JSONResponse.API_UserHiddenProfile
        
        if (
            user_info is None or 
            'statistics' not in user_info or 
            'basic' not in user_info['statistics']
        ):
            return JSONResponse.API_UserDataIsNone
        
        error, refresh = JSONResponse.extract_data(
            response=await UserStatsSyncer.refresh(account_id, user_data)
        )
        if error:
            return refresh
        
        if user_clan:
            error, result = JSONResponse.extract_data(
                response=await UserClanSyncer.refresh(account_id, user_clan)
            )
            if error:
                return result
        
        error, set_due = JSONResponse.extract_data(
            response=await PlayerModel.set_user_due(account_id)
        )
        if error:
            return set_due
        
        register_time = int(user_info.get('created_at', 0))

        data = UserRefreshResponse(
            basic={
                'region': EnvConfig.REGION,
                'user_id': account_id,
                'username': user_info['name'],
                'created_at': register_time if register_time not in (0, None) else None
            },
            credits=3
        )
        
        return JSONResponse.success(data.to_dict())
        