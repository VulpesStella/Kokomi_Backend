from typing import Literal
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader


Role = Literal["root", "user"]

class TokenManager:
    root_list = []
    user_list = []

    @classmethod
    def reload(cls, data: dict) -> tuple[int, int]:
        cls.root_list = data.get('root', [])
        cls.user_list = data.get('user', [])
        return len(cls.root_list), len(cls.user_list)

api_key_scheme = APIKeyHeader(name="Access-Token", auto_error=False)

def get_role(api_key: str = Security(api_key_scheme)) -> Role:
    if api_key in TokenManager.root_list:
        return "root"
    if api_key in TokenManager.user_list:
        return "user"
    raise HTTPException(status_code=403, detail="Invalid Access Token")

def require_user(role: Role = Security(get_role)) -> Role:
    return role

def require_root(role: Role = Security(get_role)) -> Role:
    if role != "root":
        raise HTTPException(status_code=403, detail="Root permission required")
    return role