"""Application settings loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./ai_api.db",
        alias="DATABASE_URL",
    )
    admin_bootstrap_token: str = Field(
        default="local-dev-admin-only",
        alias="ADMIN_BOOTSTRAP_TOKEN",
    )

    azure_openai_api_base: str = Field(default="", alias="AZURE_OPENAI_API_BASE")
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field(
        default="2024-06-01", alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_test_model: str = Field(
        default="gpt-4o-mini", alias="AZURE_OPENAI_TEST_MODEL"
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Phase 2: auth
    base_url: str = Field(default="http://localhost:8000", alias="BASE_URL")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str = Field(default="", alias="COOKIE_DOMAIN")
    google_oauth_client_id: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_discovery_url: str = Field(
        default="https://accounts.google.com/.well-known/openid-configuration",
        alias="GOOGLE_DISCOVERY_URL",
    )

    # Phase 2.5: hardening
    allowed_providers: list[str] = Field(default=["azure"], alias="ALLOWED_PROVIDERS")
    anomaly_check_interval_min: int = Field(default=5, alias="ANOMALY_CHECK_INTERVAL_MIN")
    anomaly_threshold_multiplier: float = Field(
        default=10.0, alias="ANOMALY_THRESHOLD_MULTIPLIER"
    )
    anomaly_absolute_cold_start: int = Field(
        default=10000, alias="ANOMALY_ABSOLUTE_COLD_START"
    )
    anomaly_min_calls: int = Field(default=100, alias="ANOMALY_MIN_CALLS")
    perip_lockout_threshold: int = Field(default=10, alias="PERIP_LOCKOUT_THRESHOLD")


@lru_cache
def get_settings() -> Settings:
    return Settings()
