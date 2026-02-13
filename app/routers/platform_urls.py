from typing import Literal
from typing import Optional
from fastapi import APIRouter, Query

from app.schemas import Server, Region, Platform
from app.apis.platform import (
    RefreshAPI, MySQLAPI, UpdateAPI, UserAPI
)

router = APIRouter()

@router.put("/refresh/vehicles/", summary="刷新船只数据")
async def searchUser(server: Server = Query(Server.WG)):
    return await RefreshAPI.refreshVehicles(server)

@router.put("/refresh/config/", summary="刷新配置参数")
async def searchUser():
    return await RefreshAPI.refreshConfig()

@router.put("/refresh/game-version/", summary="获取并更新游戏当前版本号")
async def updateGameVersion(region: Region = Query(Region.ASIA)):
    return await UpdateAPI.updateGameVersion(region)

@router.get("/permium/status/", summary="查看用户的premium信息")
async def getPermiumStatus(platform: Platform = Query(Platform.QQ_BOT), user_id: str = Query(...)):
    return await UserAPI.get_user_premium_status(platform, user_id)

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


@router.get("/generate/code/", summary="生成激活码")
async def generateCode(
    max_use: int = Query(1),
    validity: int = Query(30),
    level: int = Query(1),
    limit: int = Query(300),
    describe: Optional[str] = None
):
    return await UserAPI.generate_code(
        max_use,
        validity,
        level,
        limit,
        describe
    )