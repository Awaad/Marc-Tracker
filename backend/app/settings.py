from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Marc-Tracker"
    app_version: str = "0.1.0"
    env: str = "dev"
    cors_allow_origins: str = "*"  

    database_url: str = "sqlite+aiosqlite:///./activity_tracker.db"

    jwt_secret: str = "FROM_ENV"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 

    signal_enabled: bool = Field(default=False)
    signal_rest_base: str = Field(default="http://localhost:8080")  # signal-cli-rest-api base
    signal_account: str | None = Field(default=None)               # The linked number

    def signal_ws_url(self) -> str:
        base = self.signal_rest_base.replace("https://", "wss://").replace("http://", "ws://")
        # websocket receive endpoint
        return f"{base}/v1/receive/{self.signal_account}"


settings = Settings()
