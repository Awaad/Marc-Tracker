from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.settings import settings
from app.api.router import api_router

from app.db.models import Base
from app.db.session import engine

import logging
from app.logging_config import setup_logging

from app.middleware.request_id import RequestIdMiddleware
from app.middleware.access_log import AccessLogMiddleware


setup_logging("INFO")
log = logging.getLogger("app")
log.info("starting", extra={"env": settings.env})

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AccessLogMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allow_origins],
        allow_credentials=True,
        allow_methods=["*"],
    allow_headers=["*"],
)

    app.include_router(api_router)
    return app

app = create_app()

