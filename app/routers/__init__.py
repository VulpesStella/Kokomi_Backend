
from .platform_urls import router as platform_router
from .demo_urls import router as demo_router
from .statistics_urls import router as statistics_router
from .recent_urls import router as recent_router
from .ranking_urls import router as ranking_router
from .maintenance_urls import router as miantenance_router
from .external_urls import router as external_router

__all__ = [
    'platform_router',
    'demo_router',
    'statistics_router',
    'recent_router',
    'ranking_router',
    'miantenance_router',
    'external_router'
]