"""Shared FastAPI dependencies.

Authentication resolves the trusted ``user_id`` from a validated Cognito JWT (see
security steering) and never trusts a client-supplied identity. The validator is
built per configured user pool; when Cognito is not configured, protected routes
fail closed.

An explicit, opt-in local development bypass is available only when
``AUTH_ALLOW_LOCAL_DEV_USER`` is set AND ``APP_ENV`` is ``local``. It is ignored
in every other environment so nothing can accidentally run unauthenticated.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import Settings, get_settings
from src.core.errors import UnauthorizedError
from src.core.security.cognito import AuthenticatedUser, CognitoJwtValidator

# auto_error=False so we can raise our own consistent error envelope.
_bearer_scheme = HTTPBearer(auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _get_validator(
    issuer: str, client_id: str, jwks_url: str
) -> CognitoJwtValidator:
    """Cache one validator (and its JWKS client) per pool configuration."""
    from jwt import PyJWKClient

    return CognitoJwtValidator(
        issuer=issuer,
        client_id=client_id,
        signing_key_client=PyJWKClient(jwks_url),
    )


def get_validator(settings: SettingsDep) -> CognitoJwtValidator:
    """Provide the JWT validator; fails closed if Cognito is unconfigured."""
    if (
        not settings.cognito_issuer
        or not settings.cognito_client_id
        or not settings.cognito_jwks_url
    ):
        raise UnauthorizedError("Authentication is not configured")
    return _get_validator(
        settings.cognito_issuer,
        settings.cognito_client_id,
        settings.cognito_jwks_url,
    )


ValidatorDep = Annotated[CognitoJwtValidator, Depends(get_validator)]


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    settings: SettingsDep,
) -> AuthenticatedUser:
    """Resolve the authenticated user from the bearer token.

    Order of resolution:
    1. Local dev bypass (only if enabled AND app_env == local).
    2. Otherwise, require a bearer token and validate it against Cognito.
    """
    if settings.auth_allow_local_dev_user and settings.is_local:
        return AuthenticatedUser(user_id=settings.local_dev_user_id)

    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("A bearer token is required")

    validator = get_validator(settings)
    return validator.validate(credentials.credentials)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

__all__ = [
    "AuthenticatedUser",
    "CurrentUser",
    "SettingsDep",
    "get_current_user",
    "get_validator",
]
