from fastapi import APIRouter, Path, Query

from app.apis.ranking import ClanRankingAPI, ShipRankingAPI

router = APIRouter()


@router.get("/ship/{ship_id}/ranking/", summary="获取船只排行榜分页数据")
async def getShipRanking(
    ship_id: int = Path(..., description="船只ID"),
    page: int = Query(1, ge=1, description="页码，从 1 开始，每页 50 条")
):
    return await ShipRankingAPI.get_ship_ranking(ship_id, page)


@router.get("/ship/{ship_id}/users/{account_id}/ranking/", summary="获取用户在船只排行榜中的排名")
async def getShipUserRanking(
    ship_id: int = Path(..., description="船只ID"),
    account_id: int = Path(..., description="用户ID")
):
    return await ShipRankingAPI.get_ship_user_ranking(ship_id, account_id)


@router.get("/clan/ranking/", summary="获取工会排行榜分页数据")
async def getClanRanking(
    page: int = Query(1, ge=1, description="页码，从 1 开始，每页 50 条")
):
    return await ClanRankingAPI.get_clan_ranking(page)


@router.get("/clan/{clan_id}/ranking/", summary="获取工会在排行榜中的排名")
async def getClanSpecifyRanking(
    clan_id: int = Path(..., description="工会ID")
):
    return await ClanRankingAPI.get_clan_specify_ranking(clan_id)
