from fastapi import APIRouter

from app.schemas import ACResponse, AuthResponse
from app.apis.platform import TokenAPI

router = APIRouter()

@router.post("/token/access/", summary="设置ac")
async def setAccessToken(ac: ACResponse):
    result = await TokenAPI.set_ac(ac.account_id, ac.access_token)
    return result

@router.delete("/token/access/", summary="删除ac")
async def delAccessToken(account_id: int):
    result = await TokenAPI.del_ac(account_id)
    return result

@router.post("/token/auth/", summary="设置auth")
async def setAuthToken(auth: AuthResponse):
    result = await TokenAPI.set_auth(auth.account_id, auth.access_token, auth.expires_at)
    return result

@router.delete("/token/auth/", summary="删除auth")
async def delAuthToken(account_id: int):
    result = await TokenAPI.del_auth(account_id)
    return result
