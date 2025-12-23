from fastapi import APIRouter
from app.api.routes_health import router as health_router
from app.api.routes_stream import router as stream_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(stream_router)