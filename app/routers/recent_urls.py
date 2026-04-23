from fastapi import APIRouter

from app.response import JSONResponse

router = APIRouter()

@router.post("/accounts/{account_id}/recent/", summary="获取recent功能的基本信息")
async def enableRecent(account_id: int):
    return JSONResponse.API_1000_Success