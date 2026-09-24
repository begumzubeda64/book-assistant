"""Application configuration.

Settings are loaded from environment variables (and an optional ``.env`` file
for local development) via pydantic-settings. Secrets must never be committed;
in AWS they come from the task environment / Secrets Manager, and locally from
an untracked ``.env`` (see ``.env.example``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "dev", "prod"]


class Settings(BaseSettings):
    """Runtime configuration with safe local-first defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Book Companion API"
    app_env: AppEnv = "local"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # AWS (region is fixed to Frankfurt per tech steering)
    aws_region: str = "eu-central-1"

    # Cognito authentication. Unset locally until the pool is provisioned.
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None

    # Book discovery
    google_books_api_key: str | None = None
    book_cache_table_name: str | None = None
    book_provider_timeout_seconds: float = 8.0

    # Explicit, opt-in local auth bypass for development only. Must never be
    # enabled outside app_env=local; it is ignored in dev/prod.
    auth_allow_local_dev_user: bool = False
    local_dev_user_id: str = "local-dev-user"

    @property
    def cognito_issuer(self) -> str | None:
        """The expected JWT issuer (iss) for the configured user pool."""
        if not self.cognito_user_pool_id:
            return None
        return (
            f"https://cognito-idp.{self.aws_region}.amazonaws.com/"
            f"{self.cognito_user_pool_id}"
        )

    @property
    def cognito_jwks_url(self) -> str | None:
        """The JWKS endpoint for the configured user pool."""
        issuer = self.cognito_issuer
        return f"{issuer}/.well-known/jwks.json" if issuer else None

    # Local emulation endpoints (unset in real AWS; boto3 uses defaults there)
    dynamodb_endpoint_url: str | None = None
    aws_endpoint_url: str | None = None

    # CORS (frontend origins allowed to call the API)
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
