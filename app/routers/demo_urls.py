from fastapi import APIRouter, Query, Path

from app.schemas import Region
from app.response import JSONResponse
from app.utils import GameUtils
from app.apis.demo import (
    UserAPI, TestAPI, RecentDemoAPI
)

router = APIRouter()


@router.get("/accounts/{region}/{account_id}/db/", summary="获取用户数据库中的基本信息")
async def getUserBasic(region: Region = Path(...), account_id: int = Path(...)):
    if GameUtils.check_aid_and_rid(region, account_id) == False:
        return JSONResponse.API_2007_IllegalAccoutID
    result = await UserAPI.get_user_db_info(region, account_id)
    return result

@router.get("/brief/uid/", summary="通过uid获取用户基本信息")
async def getBriefByUID(region: Region = Query(Region.ASIA), uid: int = Query(...)):
    if GameUtils.check_aid_and_rid(region, uid) == False:
        return JSONResponse.API_2007_IllegalAccoutID
    return await UserAPI.get_base(region, uid)

@router.get("/test/error/", summary="测试错误日志功能")
async def testErrorLog():
    return await TestAPI.test_error_log()

@router.post("/feature/recent/", summary="启用recent功能")
async def enableRecent(region: Region = Query(Region.ASIA), uid: int = Query(...)):
    result = await RecentDemoAPI.demo_enable_recent(region, uid)
    return result

@router.post("/feature/recent_pro/", summary="启用recent_pro功能")
async def enableRecent(region: Region = Query(Region.ASIA), uid: int = Query(...)):
    result = await RecentDemoAPI.demo_enable_recent_pro(region, uid)
    return result

@router.delete("/feature/recent/", summary="删除recent功能")
async def enableRecent(region: Region = Query(Region.ASIA), uid: int = Query(...)):
    result = await RecentDemoAPI.demo_delete_recent(region, uid)
    return result

@router.delete("/feature/recent_pro/", summary="删除recent_pro功能")
async def enableRecent(region: Region = Query(Region.ASIA), uid: int = Query(...)):
    result = await RecentDemoAPI.demo_delete_recent_pro(region, uid)
    return result