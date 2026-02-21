from typing import Literal
from fastapi import APIRouter, Query, Path

from app.response import JSONResponse
from app.utils import GameUtils
from app.apis.demo import (
    UserAPI, TestAPI, MySQLAPI
)

router = APIRouter()


@router.get("/test/error/", summary="测试错误日志功能")
async def testErrorLog():
    return await TestAPI.test_error_log()

@router.get("/test/db_size/", summary="查看数据和缓存数据")
async def getFileSize():
    return await MySQLAPI.get_db_size()

@router.get("/mysql/overview/", summary="获取数据库概览")
async def getMySQLOverview(item: Literal['user', 'clan', 'trx', 'process']):
    if item == 'user':
        result = await MySQLAPI.get_basic_user_overview()
    elif item == 'clan':
        result = await MySQLAPI.get_basic_clan_overview()
    elif item == 'trx':
        result = await MySQLAPI.get_innodb_trx()
    else:
        result = await MySQLAPI.get_innodb_processlist()
    return result

@router.get("/accounts/{account_id}/name/", summary="获取用户数据库中的基本信息")
async def getUserBasic(account_id: int = Path(...)):
    if GameUtils.check_aid(account_id) == False:
        return JSONResponse.API_2007_IllegalAccoutID
    result = await UserAPI.get_user_db_info(account_id)
    return result

@router.get("/accounts/{account_id}/brief/", summary="获取用户基本信息")
async def getBriefByUID(uid: int = Query(...)):
    if GameUtils.check_aid(uid) == False:
        return JSONResponse.API_2007_IllegalAccoutID
    return await UserAPI.get_base(uid)