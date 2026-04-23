from fastapi import APIRouter, Query, Path

from app.schemas import ACResponse, AuthResponse
from app.apis.platform import TokenAPI, SearchAPI

router = APIRouter()

@router.get("/search/user/", summary="搜索游戏用户")
async def searchUser(
    name: str = Query(..., description="用户昵称"),
    limit: int = Query(10, description="返回结果数量限制")
):
    result = await SearchAPI.search_user(name, limit)
    return result

@router.get("/search/clan/", summary="搜索游戏工会")
async def searchClan(
    tag: str = Query(..., description="工会昵称"),
    limit: int = Query(10, description="返回结果数量限制")
):
    result = await SearchAPI.search_clan(tag, limit)
    return result

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
