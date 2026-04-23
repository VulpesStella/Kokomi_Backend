from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from .services import get_overview_data, get_api_stats_data

from app.core import EnvConfig

PROJECT_GITHUB_URL = "https://github.com/SangonomiyaKoko/Kokomi_API"

router = APIRouter()

# 模板目录
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/overview")
async def overview(request: Request):
    """概览页面"""
    data = get_overview_data()
    return templates.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "active_page": "overview",
            "node_name": f"{EnvConfig.REGION.upper()} Node",
            "github_url": PROJECT_GITHUB_URL,
            **data
        }
    )


@router.get("/api-stats")
async def api_stats(request: Request):
    """API 统计页面"""
    return templates.TemplateResponse(
        "api_stats.html",
        {
            "request": request,
            "active_page": "api_stats",
            "node_name": f"{EnvConfig.REGION.upper()} Node",
            "github_url": PROJECT_GITHUB_URL
        }
    )