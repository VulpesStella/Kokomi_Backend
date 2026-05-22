from fastapi import APIRouter, Query, Path

from app.apis.statistics import StatsAPI
from app.schemas import PVPField
from app.response import JSONResponse
from app.utils import GameUtils

router = APIRouter(prefix='/stats')

@router.get("/users/{user_id}/pvp/", summary="获取用户总体数据")
async def getUserBasic(
    user_id: int = Path(...), 
    include_old: bool = Query(True)
):
    if GameUtils.check_uid(user_id) == False:
        return JSONResponse.API_2001_IllegalAccountID
    result = await StatsAPI.get_user_pvp_overall(user_id, include_old)
    return result

# @router.get("/accounts/{account_id}/clanbattle/", summary="获取用户cw数据")
# async def getUserCW(account_id: int = Path(...)):
#     if GameUtils.check_aid(account_id) == False:
#         return JSONResponse.API_2001_IllegalAccoutID
#     result = await StatsAPI.get_user_cb(account_id)
#     return result