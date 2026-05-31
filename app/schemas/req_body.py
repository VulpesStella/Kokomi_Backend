from typing import List, Optional
from pydantic import BaseModel, Field

from .req_params import (
    ShipTier, ShipType, ShipNation
)

class ShipFilter(BaseModel):
    type: Optional[List[ShipType]] = Field(None, min_length=1)
    tier: Optional[List[ShipTier]] = Field(None, min_items=1)
    nation: Optional[List[ShipNation]] = Field(None, min_items=1)

class AuthResponse(BaseModel):
    account_id: int = Field(...)
    access_token: str = Field(...)
    expires_at: int = Field(...)
    
class ACResponse(BaseModel):
    account_id: int = Field(...)
    access_token: str = Field(...)

