from typing import Literal
from fastapi import APIRouter, Query, Path

from app.response import JSONResponse
from app.core import EnvConfig
from app.utils import GameUtils
from app.schemas import RecentLevel
from app.apis.demo import (
    TestAPI, MySQLAPI
)

router = APIRouter(prefix="/demo")


ALLOWED_TRACKING_KEYS = Literal['table_meta', 'ship_stats', 'clan_season']


@router.get("/raise_error/", summary="测试生成错误日志功能")
async def testErrorLog():
    return await TestAPI.test_error_log()


@router.delete("/error_logs/", summary="删除所有错误日志文件")
async def deleteErrorLogs():
    return await TestAPI.delete_error_logs()


@router.post("/tracking/reset/", summary="重置指定服务追踪的更新时间")
async def resetTrackingTime(
    key: ALLOWED_TRACKING_KEYS = Query(..., description="追踪服务的 Key")
):
    """
    将 T_tracking_meta 表中指定 tracking_key 的 tracking_value 置为 NULL，
    用于强制服务在下个更新轮次里触发立即刷新。
    """
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_2018_Maintenance
    
    return await MySQLAPI.reset_tracking_time(key)


@router.get("/users/{user_id}/db/", summary="获取用户数据库中的基本信息")
async def getUserDB(
    user_id: int = Path(..., description="用户ID")
):
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_2018_Maintenance
    
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    result = await MySQLAPI.get_user_overview(user_id)
    return result


@router.get("/clans/{clan_id}/db/", summary="获取工会数据库中的基本信息")
async def getClanDB(
    clan_id: int = Path(..., description="工会ID")
):
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_2018_Maintenance
    
    if not GameUtils.check_uid(clan_id):
        return JSONResponse.API_2002_IllegalClanID
    result = await MySQLAPI.get_clan_overview(clan_id)
    return result


@router.get("/users/{user_id}/basic/", summary="获取用户游戏接口中的基本信息，仅读取数据")
async def getUserAPI(
    user_id: int = Path(..., description="用户ID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    result = await TestAPI.get_user_basic(user_id)
    return result


@router.get("/users/{user_id}/clan/", summary="获取用户游戏接口中的工会信息，仅读取数据")
async def getUserAPI(
    user_id: int = Path(..., description="用户ID")
):
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    result = await TestAPI.get_user_clan(user_id)
    return result


@router.get("/clans/{clan_id}/basic/", summary="获取工会游戏接口中的基本信息，仅读取数据")
async def getUserAPI(
    clan_id: int = Path(..., description="工会ID")
):
    if not GameUtils.check_uid(clan_id):
        return JSONResponse.API_2002_IllegalClanID
    result = await TestAPI.get_clan_basic(clan_id)
    return result


@router.get("/clans/{clan_id}/members/", summary="获取工会游戏接口中的基本信息，仅读取数据")
async def getUserAPI(
    clan_id: int = Path(..., description="工会ID")
):
    if not GameUtils.check_uid(clan_id):
        return JSONResponse.API_2002_IllegalClanID
    result = await TestAPI.get_clan_members(clan_id)
    return result


@router.patch("/users/{user_id}/features/", summary="启用记录玩家近期数据的功能")
async def enable_features(
    user_id: int = Path(..., description="用户ID"),
    level: RecentLevel = Query(RecentLevel.standard, description="功能等级")
):
    """[DEMO] 启用记录玩家近期数据的功能
    
    - standard: 启用基础的近期数据记录
    - plus: 启用详细的近期数据记录
    """
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_2018_Maintenance
    
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    
    return await TestAPI.set_recent(user_id, level.value)


@router.delete("/users/{user_id}/features/", summary="关闭用户记录近期数据的功能")
async def disable_features(
    user_id: int = Path(..., description="用户ID"),
    level: RecentLevel = Query(RecentLevel.off, description="目标等级")
):
    """[DEMO] 关闭用户记录近期数据的功能
    
    - off: 完全关闭近期数据记录
    - standard: 从Plus降级到标准版
    """
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_2018_Maintenance
    
    if not GameUtils.check_uid(user_id):
        return JSONResponse.API_2001_IllegalAccountID
    
    return await TestAPI.del_recent(user_id, level.value)