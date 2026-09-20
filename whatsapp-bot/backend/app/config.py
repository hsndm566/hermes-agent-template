from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    evolution_internal_url: str
    evolution_api_key: str
    evolution_webhook_url: str
    app_public_url: str
    admin_username: str
    admin_password: str
    session_secret: str
    session_max_age_seconds: int = 43200
    tz: str = "Asia/Riyadh"
    enable_test_mode: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
