from fastapi import APIRouter, Query, Path

from app.response import JSONResponse
from app.utils import GameUtils
from app.schemas import RecentLevel
from app.apis.demo import (
    TestAPI, MySQLAPI
)

router = APIRouter()


@router.get("/raise_error/", summary="测试生成错误日志功能")
async def testErrorLog():
    return await TestAPI.test_error_log()

@router.get("/user/{user_id}/db/", summary="获取用户数据库中的基本信息")
async def getUserDB(
    user_id: int = Path(..., description="游戏玩家UID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    result = await MySQLAPI.get_user_overview(user_id)
    return result

@router.get("/clan/{clan_id}/db/", summary="获取工会数据库中的基本信息")
async def getClanDB(
    clan_id: int = Path(..., description="游戏工会UID")
):
    if not GameUtils.check_uid(clan_id):
        return JSONResponse.API_2002_IllegalClanID
    result = await MySQLAPI.get_clan_overview(clan_id)
    return result

@router.get("/user/{user_id}/basic/", summary="获取用户游戏接口中的基本信息，仅读取数据")
async def getUserAPI(
    user_id: int = Path(..., description="游戏玩家UID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    result = await TestAPI.get_user_basic(user_id)
    return result

@router.get("/clan/{clan_id}/basic/", summary="获取工会游戏接口中的基本信息，仅读取数据")
async def getUserAPI(
    clan_id: int = Path(..., description="游戏工会UID")
):
    if not GameUtils.check_uid(clan_id):
        return JSONResponse.API_2002_IllegalClanID
    result = await TestAPI.get_clan_basic(clan_id)
    return result

@router.get("/user/{user_id}/clan/", summary="获取用户游戏接口中的工会信息，仅读取数据")
async def getUserAPI(
    user_id: int = Path(..., description="游戏玩家UID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    result = await TestAPI.get_user_clan(user_id)
    return result

@router.patch("/user/{user_id}/features/", summary="启用记录玩家近期数据的功能")
async def enable_features(
    user_id: int = Path(..., description="游戏玩家UID"),
    level: RecentLevel = Query(RecentLevel.standard, description="功能等级")
):
    """[DEMO] 启用记录玩家近期数据的功能
    
    - standard: 启用基础的近期数据记录
    - plus: 启用详细的近期数据记录
    """
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    
    return await TestAPI.set_recent(user_id, level.value)

@router.delete("/user/{user_id}/features/", summary="关闭用户记录近期数据的功能")
async def disable_features(
    user_id: int = Path(..., description="游戏玩家UID"),
    level: RecentLevel = Query(RecentLevel.off, description="目标等级")
):
    """[DEMO] 关闭用户记录近期数据的功能
    
    - off: 完全关闭近期数据记录
    - standard: 从Plus降级到标准版
    """
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    
    return await TestAPI.del_recent(user_id, level.value)