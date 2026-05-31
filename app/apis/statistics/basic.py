from app.core import EnvConfig
from app.response import JSONResponse
from app.loggers import ExceptionLogger
from app.models import PlayerModel, UserStatsSyncer
from app.network import ExternalAPI

class BasicAPI:
    @ExceptionLogger.handle_program_exception_async
    async def get_user_basic(account_id: int, access_token: str = None):
        if EnvConfig.DEV_MODE:
            user = None
        else:
            # 先读数据库，读不到数据再请求
            error, user = JSONResponse.extract_data_strict(
                response=await PlayerModel.get_user_name_and_clan(account_id)
            )
            if error:
                return user
        
        if user is None or not user['stats']:
            error, response = JSONResponse.extract_data_strict(
                response=await ExternalAPI.get_user_basic(account_id, access_token)
            )
            if error:
                return response
            
            user_info = response.get(str(account_id))

            if user_info is None:
                return JSONResponse.API_2011_UserNotExist
            
            if 'hidden_profile' in user_info:
                return JSONResponse.API_2015_UserHiddenProfile
            
            if (
                user_info is None or 
                'statistics' not in user_info or 
                'basic' not in user_info['statistics']
            ):
                return JSONResponse.API_2013_UserDataIsNone
            
            if not EnvConfig.DEV_MODE:
                error, refresh = JSONResponse.extract_data_strict(
                    response=await UserStatsSyncer.refresh(account_id, response)
                )
                if error:
                    return refresh
            
            statistics = user_info['statistics']
            basic_data = statistics.get('basic', {})
            leveling_points = basic_data.get('leveling_points', 0)
            if leveling_points >= 1_000_000:
                leveling_points -= 1_000_000
            
            if leveling_points == 0:
                return JSONResponse.API_2013_UserDataIsNone
            
            register_time = int(user_info.get('created_at', 0))
            
            user_basic = {
                'region': EnvConfig.REGION,
                'user_id': account_id,
                'username': user_info['name'],
                'clan_id': None,
                'clan_tag': None,
                'league': None,
                'karma': user_info.get('karma', 0),
                'created_at': register_time if register_time not in (0, None) else None,
                'insignias': user_info.get('dog_tag')
            }
        else:
            user_basic = user['basic']

        return JSONResponse.get_success_response(user_basic)