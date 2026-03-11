"""환경 변수 설정 관리."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    cfj_database_url: str = (
        "postgresql+asyncpg://postgres:postgres@postgres:5432/core_film_journal"
    )
    redis_url: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
