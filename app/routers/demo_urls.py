from typing import Literal
from fastapi import APIRouter, Query, Path

from app.response import JSONResponse
from app.utils import GameUtils
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
        return JSONResponse.API_2001_IllegalAccoutID
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
        return JSONResponse.API_2001_IllegalAccoutID
    result = await TestAPI.get_user_basic(user_id)
    return result

@router.get("/user/{user_id}/clan/", summary="获取用户游戏接口中的工会信息，仅读取数据")
async def getUserAPI(
    user_id: int = Path(..., description="游戏玩家UID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccoutID
    result = await TestAPI.get_user_clan(user_id)
    return result

@router.get("/user/{user_id}/header/", summary="获取用户游戏接口中的基本和工会信息，读取数据并更新数据库")
async def getUserAPI(
    user_id: int = Path(..., description="游戏玩家UID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccoutID
    result = await TestAPI.get_user_header(user_id)
    return result

@router.patch("/user/{user_id}/features/", summary="启用记录玩家近期数据的功能")
async def enableFeatures(
    user_id: int = Path(..., description="游戏玩家UID"),
    level: int = Query(..., description="等级", ge=1, le=2)
):
    """[DEMO] 启用记录玩家近期数据的功能

    level 1: 记录基础的近期数据
    level 2: 记录详细的近期数据
    """
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccoutID
    if level == 2:
        return await TestAPI.set_recents(user_id)
    else:
        return await TestAPI.set_recent(user_id)

@router.delete("/user/{user_id}/features/", summary="关闭用户记录近期数据的功能")
async def enableFeatures(
    user_id: int = Path(..., description="游戏玩家UID"),
    level: int = Query(..., description="等级", ge=1, le=2)
):
    """[DEMO] 关闭用户记录近期数据的功能

    level 1: 记录所有近期数据的记录

    level 2: 关闭详细的近期数据的记录，保留基础的近期数据的记录
    """
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccoutID
    if level == 2:
        return await TestAPI.del_recents(user_id)
    else:
        return await TestAPI.del_recent(user_id)