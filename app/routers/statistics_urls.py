from fastapi import APIRouter, Query, Path
from typing import Optional

from app.response import JSONResponse
from app.utils import GameUtils
from app.schemas import ShipTier, ShipType, ShipNation, PVPField
from app.apis.statistics import PVEAPI, RandomAPI, RankedAPI


router = APIRouter(prefix='/stats')

@router.get("/users/{user_id}/pve/overall/", summary="获取用户人机战斗总体数据")
async def getPvEOverall(
    user_id: int = Path(..., description="用户ID"),
    include_old: Optional[bool] = Query(None, description="是否包含旧船")
):
    if GameUtils.check_uid(user_id) == False:
        return JSONResponse.API_IllegalAccountID
    
    if include_old is None:
        include_old = True

    return await PVEAPI.overall(user_id, include_old)

@router.get("/users/{user_id}/random/overall/", summary="获取用户随机战斗总体数据")
async def getPvPOverall(
    user_id: int = Path(..., description="用户ID"),
    field: Optional[PVPField] = Query(None, description="数据类型"),
    ship_tier: Optional[ShipTier] = Query(None, description="船只等级"),
    ship_type: Optional[ShipType] = Query(None, description="船只类型"),
    ship_nation: Optional[ShipNation] = Query(None, description="船只国籍"),
    include_old: Optional[bool] = Query(None, description="是否包含旧船")
):
    if GameUtils.check_uid(user_id) == False:
        return JSONResponse.API_IllegalAccountID
    
    if include_old is None:
        include_old = True
    
    filter_params = {
        "field": field,
        "tier": ship_tier,
        "type": ship_type,
        "nation": ship_nation
    }
    provided_filters = [name for name, val in filter_params.items() if val is not None]
    if len(provided_filters) > 1:
        return JSONResponse.API_InvalidFilter
    
    if not provided_filters:
        filter_type = "overall"
    else:
        filter_field = provided_filters[0]
        filter_value = filter_params[filter_field]
        if filter_field == 'field':
            filter_type = filter_value.value.upper()
        elif filter_field == 'tier':
            filter_type = GameUtils.format_tier(filter_value.value)
        elif filter_field == 'nation':
            filter_type = GameUtils.format_nation(filter_value.value)
        else:
            filter_type = str(filter_value.value)
    
    
    if field:
        return await RandomAPI.field(
            user_id,
            filter_type,
            field,
            include_old
        )
    else:
        return await RandomAPI.overall(
            user_id,
            filter_type,
            ship_tier.value if ship_tier is not None else None,
            ship_type.value if ship_type is not None else None,
            ship_nation.value if ship_nation is not None else None,
            include_old
        )

@router.get("/users/{user_id}/ranked/overall/", summary="获取用户排位战斗总体数据")
async def getRankedOverall(
    user_id: int = Path(..., description="用户ID"),
    include_old: Optional[bool] = Query(None, description="是否包含旧船")
):
    if GameUtils.check_uid(user_id) == False:
        return JSONResponse.API_IllegalAccountID
    
    if include_old is None:
        include_old = True

    return await RankedAPI.overall(
        user_id,
        include_old
    )