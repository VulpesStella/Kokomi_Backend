from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from .services import get_overview_data, get_celery_data, get_game_api_data, get_database_data, get_user_activity_data

from app.core import EnvConfig

PROJECT_GITHUB_URL = "https://github.com/SangonomiyaKoko/Kokomi_Backend"

router = APIRouter()

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _node_info():
    return {
        "Region": EnvConfig.REGION.upper(),
        "Timezone": EnvConfig.REGION_TIMEZONE,
        "Location": EnvConfig.LOCATION,
        "Init Time": EnvConfig.INIT_TIME,
    }


def _render(request: Request, template: str, active_page: str, data: dict):
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "active_page": active_page,
            "node_name": f"{EnvConfig.REGION.upper()} Node",
            "github_url": PROJECT_GITHUB_URL,
            "node_info": _node_info(),
            **data,
        },
    )


@router.get("/overview")
async def overview(request: Request):
    return _render(request, "overview.html", "overview", await get_overview_data())


@router.get("/game-api")
async def api_stats(request: Request):
    return _render(request, "game_api.html", "game-api", await get_game_api_data())


@router.get("/celery")
async def celery_stats(request: Request):
    return _render(request, "celery.html", "celery", await get_celery_data())


@router.get("/database")
async def database_stats(request: Request):
    return _render(request, "database.html", "database", await get_database_data())


@router.get("/update-plans")
async def update_plans(request: Request):
    return _render(request, "update_plans.html", "update-plans", await get_user_activity_data())
