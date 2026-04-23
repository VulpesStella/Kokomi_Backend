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

@router.get("/db/sqlite3/overview/", summary="获取sqlite3数据库概览")
async def getFileSize():
    return await MySQLAPI.get_recent_overview()

@router.get("/db/mysql/overview/", summary="获取mysql数据库概览")
async def getMySQLOverview():
    result = await MySQLAPI.get_overview()
    return result

@router.get("/db/account/{account_id}/", summary="获取用户数据库中的基本信息")
async def getUserDB(
    account_id: int = Path(..., description="游戏用户UID")
):
    if not GameUtils.check_uid(account_id):
        return JSONResponse.API_2001_IllegalAccoutID
    result = await MySQLAPI.get_user_overview(account_id)
    return result

@router.get("/db/clan/{clan_id}/", summary="获取工会数据库中的基本信息")
async def getClanDB(
    clan_id: int = Path(..., description="游戏工会UID")
):
    if not GameUtils.check_uid(clan_id):
        return JSONResponse.API_2002_IllegalClanID
    result = await MySQLAPI.get_clan_overview(clan_id)
    return result

@router.get("/api/account/{account_id}/", summary="获取用户游戏接口中的基本信息")
async def getUserAPI(
    account_id: int = Path(..., description="游戏用户UID")
):
    if not GameUtils.check_uid(account_id):
        return JSONResponse.API_2001_IllegalAccoutID
    result = await TestAPI.get_user_base(account_id)
    return result