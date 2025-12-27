from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Marc-Tracker"
    app_version: str = "0.1.0"
    env: str = "dev"
    cors_allow_origins: str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    database_url: str = "sqlite+aiosqlite:///./activity_tracker.db"

    jwt_secret: str = "FROM_ENV"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 

    signal_enabled: bool = Field(default=False)
    signal_rest_base: str = Field(default="http://localhost:8080")  # signal-cli-rest-api base
    signal_account: str | None = Field(default=None)               # The linked number

    whatsapp_enabled: bool = Field(default=False)
    whatsapp_graph_base: str = Field(default="https://graph.facebook.com/v21.0")
    whatsapp_phone_number_id: str | None = Field(default=None)
    whatsapp_access_token: str | None = Field(default=None)

    # webhook verification + signature (used in commit 25)
    whatsapp_verify_token: str | None = Field(default=None)
    whatsapp_app_secret: str | None = Field(default=None)

    # WhatsApp Web (unofficial) adapter settings
    whatsapp_web_enabled: bool = False
    whatsapp_web_bridge_base: str = "http://localhost:8099"
    whatsapp_web_bridge_ws: str = "ws://localhost:8099/events"


    SMTP_HOST: str = "smtp.emailit.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "emailit"
    SMTP_PASS: str = "3OBhqpXA9efW7A"
    SMTP_FROM: str = "example@example.com"
    ADMIN_NOTIFY_EMAIL: str = "example@gmail.com"

    def signal_ws_url(self) -> str:
        base = self.signal_rest_base.replace("https://", "wss://").replace("http://", "ws://")
        # websocket receive endpoint
        return f"{base}/v1/receive/{self.signal_account}"


settings = Settings()
