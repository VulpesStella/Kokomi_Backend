from fastapi import HTTPException
from fastapi import APIRouter, Path, Query

from app.apis.ranking import ClanRankingAPI, ShipRankingAPI

router = APIRouter(prefix="/ranking")


@router.get("/ship/{ship_id}/", summary="获取船只排行榜分页数据")
async def getShipRanking(
    ship_id: int = Path(..., description="船只ID"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(50, ge=50, le=100, description="每页条数，只能选 50 或 100")
):
    if size not in (50, 100):
        raise HTTPException(status_code=422, detail="Page size must be 50 or 100")
    return await ShipRankingAPI.get_ship_ranking(ship_id, page, size)


@router.get("/ship/{ship_id}/users/{user_id}/", summary="获取用户在船只排行榜中的排名")
async def getShipUserRanking(
    ship_id: int = Path(..., description="船只ID"),
    user_id: int = Path(..., description="用户ID"),
    size: int = Query(50, ge=50, le=100, description="每页条数，只能选 50 或 100")
):
    if size not in (50, 100):
        raise HTTPException(status_code=422, detail="Page size must be 50 or 100")
    return await ShipRankingAPI.get_ship_user_ranking(ship_id, user_id, size)


@router.get("/clan/", summary="获取工会排行榜分页数据")
async def getClanRanking(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(50, ge=50, le=100, description="每页条数，只能选 50 或 100")
):
    if size not in (50, 100):
        raise HTTPException(status_code=422, detail="Page size must be 50 or 100")
    return await ClanRankingAPI.get_clan_ranking(page, size)


@router.get("/clan/{clan_id}/", summary="获取指定工会在排行榜中的排名及所在页数据")
async def getClanUserRanking(
    clan_id: int = Path(..., description="工会ID"),
    size: int = Query(50, ge=50, le=100, description="每页条数，只能选 50 或 100")
):
    if size not in (50, 100):
        raise HTTPException(status_code=422, detail="Page size must be 50 or 100")
    return await ClanRankingAPI.get_clan_user_ranking(clan_id, size)
