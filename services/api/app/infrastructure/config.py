from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = Field(min_length=1)
    redis_url: str = Field(min_length=1)
    allowed_origins: str = "http://localhost:3000"
    app_environment: Literal["development", "production"] = "development"
    auth_cookie_secure: bool = False
    auth_login_account_limit: int = Field(default=10, ge=1, le=100)
    auth_login_source_limit: int = Field(default=60, ge=1, le=1000)
    auth_register_source_limit: int = Field(default=5, ge=1, le=100)
    enable_qq_provider: bool = True
    enable_music_providers: bool = True
    enable_musicbrainz_provider: bool = True
    brave_search_api_key: SecretStr | None = None
    llm_provider: Literal["local", "openai_compatible"] = "local"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=100)
    agent_timeout_seconds: float = Field(default=90, ge=1, le=120)

    @field_validator("llm_base_url")
    @classmethod
    def valid_llm_url(cls, value: str) -> str:
        url = urlparse(value)
        if (url.scheme not in ("https", "http") or not url.hostname or url.username
                or url.password or url.query or url.fragment
                or (url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1"))):
            raise ValueError("LLM_BASE_URL requires HTTPS (HTTP only on loopback)")
        return value

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

    @field_validator("allowed_origins")
    @classmethod
    def valid_origins(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",")]
        if not origins or any(urlparse(item).scheme not in ("http", "https") or
                              not urlparse(item).hostname or "*" in item or urlparse(item).path or
                              urlparse(item).query or urlparse(item).fragment or
                              urlparse(item).username for item in origins):
            raise ValueError("ALLOWED_ORIGINS requires exact HTTP(S) origins")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
