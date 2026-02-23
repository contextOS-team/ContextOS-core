"""Main API router that aggregates all sub-routers."""

from fastapi import APIRouter

from src.api.routes.context import router as context_router
from src.api.routes.search import router as search_router
from src.api.routes.tickets import router as tickets_router
from src.api.routes.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(context_router, prefix="/context", tags=["context"])
api_router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
