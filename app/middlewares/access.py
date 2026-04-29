from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
from enum import Enum
from typing import Optional

from app.core import EnvConfig


class Role(str, Enum):
    ROOT = "root"
    USER = "user"


class SecurityManager:
    _api_key_scheme = APIKeyHeader(name="Access-Token", auto_error=False)
    
    @classmethod
    def _get_config(cls):
        try:
            return EnvConfig.get_config()
        except RuntimeError:
            raise HTTPException(status_code=500, detail="Configuration not initialized")
    
    @classmethod
    def _validate_api_key(cls, api_key: Optional[str]) -> str:
        """验证 API Key 并返回角色"""
        if not api_key:
            raise HTTPException(status_code=403, detail="Missing Access Token")
        
        config = cls._get_config()
        
        if api_key == config.SECURITY.root:
            return Role.ROOT
        elif api_key == config.SECURITY.user:
            return Role.USER
        else:
            raise HTTPException(status_code=403, detail="Invalid Access Token")
    
    @classmethod
    async def require_root(cls, api_key: str = Security(_api_key_scheme)) -> bool:
        """要求 Root 权限"""
        role = cls._validate_api_key(api_key)
        if role == Role.ROOT:
            return True
        raise HTTPException(status_code=403, detail="Root permission required")
    
    @classmethod
    async def require_user(cls, api_key: str = Security(_api_key_scheme)) -> bool:
        """要求 User 或 Root 权限"""
        role = cls._validate_api_key(api_key)
        if role in [Role.ROOT, Role.USER]:
            return True
        raise HTTPException(status_code=403, detail="User permission required")
    
    @classmethod
    async def get_current_role(cls, api_key: str = Security(_api_key_scheme)) -> str:
        """获取当前用户角色"""
        return cls._validate_api_key(api_key)