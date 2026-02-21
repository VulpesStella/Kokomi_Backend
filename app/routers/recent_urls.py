from fastapi import APIRouter

from app.apis.recent import RecentManagerAPI

router = APIRouter()

@router.post("/accounts/{account_id}/recent/", summary="启用recent功能")
async def enableRecent(account_id: int):
    result = await RecentManagerAPI.enable_recent(account_id)
    return result

@router.delete("/accounts/{account_id}/recent/", summary="关闭recent功能")
async def deleteRecent(account_id: int):
    result = await RecentManagerAPI.delete_recent(account_id)
    return result

@router.post("/accounts/{account_id}/daily/", summary="启用daily功能")
async def enableRecentPro(account_id: int):
    result = await RecentManagerAPI.enable_recent_pro(account_id)
    return result

@router.delete("/accounts/{account_id}/daily/", summary="关闭daily功能")
async def deleteRecentPro(account_id: int):
    result = await RecentManagerAPI.delete_recent_pro(account_id)
    return result