import sys
import psutil
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import FileResponse

from app.core import EnvConfig, AppState
from app.response import JSONResponse
from app.schemas import RankingFileType
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

@router.get("/system/", summary="系统的基本信息")
def system_stats():
    is_linux = sys.platform.startswith('linux')
    return {
        "cpu": psutil.cpu_percent(interval=0.2),
        "mem": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent if is_linux else None
    }

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
async def download_ranking_msgpack(
    file_type: RankingFileType = Query(RankingFileType.SHIP_RANKING,description="文件类型")
):
    """下载 ranking.msgpack 文件"""
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    file_path = EnvConfig.DATA_DIR / f'trash/{file_type.value}.msgpack'
    
    # 检查文件是否存在
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File {file_type.value}.msgpack does not exist"
        )
    
    # 返回文件作为下载响应
    return FileResponse(
        path=file_path,
        filename=f"{file_type.value}.msgpack",
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={file_type.value}.msgpack"
        }
    )