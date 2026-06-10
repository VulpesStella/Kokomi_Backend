from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core import EnvConfig, AppState
from app.response import JSONResponse
from app.middlewares import RedisClient
from app.apis.maintenance import MaintenanceAPI


router = APIRouter(prefix="/maintenance")

@router.get("/state/", summary="获取当前状态")
async def get_app_state():
    """返回当前应用是否可用的全局状态"""
    result = {
        "available": AppState.is_available()
    }
    return JSONResponse.success(result)


@router.put("/state/", summary="设置应用可用状态")
async def set_app_state(available: bool = Query(..., description="设置应用是否可用")):
    """设置应用是否可用的全局状态，传入 True 或 False"""
    if EnvConfig.DEV_MODE:
        return JSONResponse.API_NodeNotAvailable
    
    key = 'status:maintenance'

    if available:
        error, response = JSONResponse.extract_data(
            response=await RedisClient.drop(key)
        )
    else:
        error, response = JSONResponse.extract_data(
            response=await RedisClient.set(key, 1)
        )
    if error:
        return response
    
    AppState.set_available(available)

    result = {
        "available": AppState.is_available()
    }
    return JSONResponse.success(result)

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