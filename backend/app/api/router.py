from fastapi import APIRouter
from app.api.routes_health import router as health_router
from app.api.routes_stream import router as stream_router
from app.api.routes_auth import router as auth_router
from app.api.routes_contacts import router as contacts_router
from app.api.routes_tracking import router as tracking_router
from app.api.routes_points import router as points_router
from app.api.routes_probes import router as probes_router
from app.api.routes_webhooks_whatsapp import router as whatsapp_webhooks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(stream_router)
api_router.include_router(contacts_router)
api_router.include_router(tracking_router)
api_router.include_router(points_router)
api_router.include_router(probes_router)
api_router.include_router(whatsapp_webhooks_router)