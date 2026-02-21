from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

from app.core import EnvConfig


api_key_scheme = APIKeyHeader(name="Access-Token", auto_error=False)

def get_role(api_key: str = Security(api_key_scheme)) -> bool:
    if api_key == EnvConfig.config.API_TOKEN:
        return 'root'
    raise HTTPException(status_code=403, detail="Invalid Access Token")