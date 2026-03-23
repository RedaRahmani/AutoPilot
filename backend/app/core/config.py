from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AutoPilot"
    app_env: str = "development"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "autopilot"
    postgres_user: str = "autopilot"
    postgres_password: str
    database_url: str | None = None

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None

    service_wait_timeout: int = 60
    service_wait_interval: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
