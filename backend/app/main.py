from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.settings import settings
from app.api.router import api_router

from app.db.models import Base
from app.db.session import engine


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )

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

@app.on_event("startup")
async def _startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)