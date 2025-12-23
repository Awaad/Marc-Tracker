from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.settings import settings
from app.api.router import api_router

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