from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import FileResponse

from app.core import EnvConfig, AppState
from app.response import JSONResponse
from app.utils import GameUtils
from app.apis.manager import (
    StateAPI, 
    MaintenanceAPI, 
    UserManagerAPI
)


router = APIRouter(prefix="/maintenance")

@router.get("/state/", summary="获取当前状态")
async def get_app_state():
    """返回当前应用是否可用的全局状态"""
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    return await StateAPI.get_node_state()


@router.put("/state/", summary="设置应用可用状态")
async def set_app_state(available: bool = Query(..., description="设置应用是否可用")):
    """设置应用是否可用的全局状态，传入 True 或 False"""
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    return await StateAPI.set_node_state(available)

@router.post("/user/{user_id}/", summary="平台拉黑用户并清除排行榜数据")
async def getPvEOverall(
    user_id: int = Path(..., description="用户ID")
):
    # 检查应用状态
    if not AppState.is_available():
        return JSONResponse.API_NodeNotAvailable
    
    if GameUtils.check_uid(user_id) == False:
        raise HTTPException(status_code=422, detail="Invalid UID")

    return await UserManagerAPI.block_user(user_id)

@router.get("/database/meta/", summary="数据库统计指标")
async def getDatabaseMeta():
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    return await MaintenanceAPI.get_database_meta()

@router.get("/ship/stats/", summary="船只服务器数据")
async def getShipStats():
    # DEPRECATED: 该接口后续将弃用
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    return await MaintenanceAPI.get_ship_stats()

@router.get("/ranking/download/", summary="下载排行榜数据文件")
async def download_ranking_msgpack():
    """下载 ranking.msgpack 文件"""
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    file_path = EnvConfig.DATA_DIR / 'trash/ranking.msgpack'
    
    # 检查文件是否存在
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File does not exist"
        )
    
    # 返回文件作为下载响应
    return FileResponse(
        path=file_path,
        filename="ranking.msgpack",  # 下载时的文件名
        media_type="application/octet-stream",  # 二进制文件类型
        headers={
            "Content-Disposition": "attachment; filename=ranking.msgpack"
        }
    )