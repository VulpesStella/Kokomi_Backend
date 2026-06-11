from app.loggers import ExceptionLogger
from app.middlewares import RedisClient, BlacklistManager
from app.response import JSONResponse, ResponseDict
from app.models import DemoPlayerModel, PlayerModel, ShipModel

class UserManagerAPI:
    @ExceptionLogger.handle_program_exception_async
    async def block_user(account_id: int) -> ResponseDict:
        BlacklistManager.add_user(account_id)
        
        error, ship_ids = JSONResponse.extract_data(
            response=await ShipModel.get_ranking_ship_ids()
        )
        if error:
            return ship_ids
        
        # 将该 ID 直接设为不可用
        error, status = JSONResponse.extract_data(
            response=await DemoPlayerModel.set_user_status(account_id, 0)
        )
        if error:
            return status
        
        # 读取用户已缓存的数据
        error, user_cache = JSONResponse.extract_data(
            response=await PlayerModel.get_user_cache(account_id)
        )
        if error:
            return status
        
        delete_ids = []
        for ship_id, ship_data in user_cache.items():
            if int(ship_id) not in ship_ids:
                continue
            min_battles = ship_ids.get(int(ship_id))
            if ship_data[0] >= min_battles:
                delete_ids.append(ship_id)

        if len(delete_ids) > 0:
            # 先删除redis缓存
            error, deleted = JSONResponse.extract_data(
                response=await RedisClient.zrem_member(
                    [f'leaderboard:ship:{sid}' for sid in delete_ids], 
                    str(account_id)
                )
            )
            if error:
                return deleted
            
            # 再删除mysql数据
            error, deleted = JSONResponse.extract_data(
                response=await DemoPlayerModel.remove_user_ranking(account_id, delete_ids)
            )
            if error:
                return deleted
            
        return JSONResponse.API_1000_Success
            
