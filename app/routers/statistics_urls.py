from fastapi import APIRouter, Query, Path

from app.apis.statistics import StatsAPI, RankingAPI
from app.schemas import PVPField
from app.response import JSONResponse
from app.utils import GameUtils

router = APIRouter()


@router.patch("/accounts/{account_id}/", summary="刷新用户基本信息的缓存")
async def getUserBasic(account_id: int = Path(...)):
    if GameUtils.check_uid(account_id) == False:
        return JSONResponse.API_2001_IllegalAccoutID
    result = await StatsAPI.refresh_user_cache(account_id)
    return result

# @router.post("/leaderboard/{ship_id}/top50/", summary="获取船只排行榜的前50名玩家")
# async def getUserBasic(ship_id: int = Path(...)):
#     result = await RankingAPI.get_region_top(ship_id)
#     return result

# @router.get("/accounts/{account_id}/overall/", summary="获取用户总体数据")
# async def getUserBasic(
#     account_id: int = Path(...), 
#     field: PVPField = Query(PVPField.PVP),
#     include_old: bool = Query(True)
# ):
#     if GameUtils.check_uid(account_id) == False:
#         return JSONResponse.API_2001_IllegalAccoutID
#     result = await StatsAPI.get_user_pvp(account_id, field, include_old)
#     return result

# @router.get("/accounts/{account_id}/clanbattle/", summary="获取用户cw数据")
# async def getUserCW(account_id: int = Path(...)):
#     if GameUtils.check_aid(account_id) == False:
#         return JSONResponse.API_2001_IllegalAccoutID
#     result = await StatsAPI.get_user_cb(account_id)
#     return result