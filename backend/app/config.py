from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str
    database_url: str
    brevo_api_key: str = ""
    email_sender_address: str = ""
    email_sender_name: str = "Losowanie prezentów"
    cors_origins: str = "http://localhost:3000"
    min_participants: int = 3
    email_cooldown_minutes: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
