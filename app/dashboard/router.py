from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from .services import get_overview_data

from app.core import EnvConfig

PROJECT_GITHUB_URL = "https://github.com/SangonomiyaKoko/Kokomi_API"

router = APIRouter()

# 模板目录
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/overview")
async def overview(request: Request):
    """概览页面"""
    data = await get_overview_data()
    node_info = {
        "Region": EnvConfig.REGION.upper(),
        "Timezone": EnvConfig.REGION_TIMEZONE,
        "Location": EnvConfig.LOCATION ,
        "Init Time": EnvConfig.INIT_TIME
    }
    return templates.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "active_page": "overview",
            "node_name": f"{EnvConfig.REGION.upper()} Node",
            "github_url": PROJECT_GITHUB_URL,
            "node_info": node_info,
            **data
        }
    )


@router.get("/game-api")
async def api_stats(request: Request):
    """API 统计页面"""
    node_info = {
        "Region": EnvConfig.REGION.upper(),
        "Timezone": EnvConfig.REGION_TIMEZONE,
        "Location": EnvConfig.LOCATION ,
        "Init Time": EnvConfig.INIT_TIME
    }
    return templates.TemplateResponse(
        "game_api.html",
        {
            "request": request,
            "active_page": "game-api",
            "node_name": f"{EnvConfig.REGION.upper()} Node",
            "github_url": PROJECT_GITHUB_URL,
            "node_info": node_info
        }
    )