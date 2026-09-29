from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = Field(min_length=1)
    redis_url: str = Field(min_length=1)
    allowed_origins: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def valid_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql+psycopg://", "sqlite+pysqlite://")):
            raise ValueError("DATABASE_URL must use PostgreSQL/psycopg (SQLite is test-only)")
        url = make_url(value)
        if url.drivername == "postgresql+psycopg" and (not url.host or not url.database):
            raise ValueError("DATABASE_URL needs a host and database")
        return value

    @field_validator("redis_url")
    @classmethod
    def valid_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        if not urlparse(value).hostname:
            raise ValueError("REDIS_URL needs a host")
        return value

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
