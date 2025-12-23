from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Marc-Tracker"
    app_version: str = "0.1.0"
    env: str = "dev"
    cors_allow_origins: str = "*"  

    database_url: str = "sqlite+aiosqlite:///./activity_tracker.db"


settings = Settings()
