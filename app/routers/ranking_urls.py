from typing import Literal
from fastapi import APIRouter, Query, Path

from app.response import JSONResponse
from app.utils import GameUtils
from app.apis.demo import (
    TestAPI, MySQLAPI
)

router = APIRouter()


@router.get("/ship/{ship_id}/top50/", summary="获取船只排行版Top50")
async def getShipTop50():
    return await TestAPI.test_error_log()