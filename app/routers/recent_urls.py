from fastapi import APIRouter, Query, Path

from app.core import EnvConfig
from app.response import JSONResponse
from app.apis.recent import RecentAPI
from app.utils import GameUtils

router = APIRouter(prefix='/recent')

@router.get("/users/{user_id}/summary/", summary="获取用户近期数据概览")
async def getRecentSummary(
    user_id: int = Path(..., description="用户ID"),
):
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_2018_Maintenance
    
    if GameUtils.check_uid(user_id) == False:
        return JSONResponse.API_2001_IllegalAccountID
    
    result = await RecentAPI.summary(user_id)

    return result

# @router.get("/users/{user_id}/random/", summary="获取用户近期随机数据")
# async def getRandomRecent(
#     user_id: int = Path(..., description="用户ID"),
# ):
#     if EnvConfig.DEV_MODE:
#         return JSONResponse.API_2018_Maintenance
    
#     if GameUtils.check_uid(user_id) == False:
#         return JSONResponse.API_2001_IllegalAccountID
    
#     result = await RecentAPI.ranked(user_id, None, None)

#     return result

# @router.get("/users/{user_id}/ranked/", summary="获取用户近期排位数据")
# async def getRankedRecent(
#     user_id: int = Path(..., description="用户ID"),
# ):
#     if EnvConfig.DEV_MODE:
#         return JSONResponse.API_2018_Maintenance
    
#     if GameUtils.check_uid(user_id) == False:
#         return JSONResponse.API_2001_IllegalAccountID
    
#     result = await RecentAPI.ranked(user_id, None, None)

#     return result