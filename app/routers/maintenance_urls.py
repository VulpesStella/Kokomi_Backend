from fastapi import APIRouter

from app.apis.maintenance import MaintenanceAPI

router = APIRouter(prefix="/maintenance")


@router.get("/database/meta/", summary="数据库统计指标")
async def getDatabaseMeta():
    return await MaintenanceAPI.get_database_meta()