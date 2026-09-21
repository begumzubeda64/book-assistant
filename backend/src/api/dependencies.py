"""Shared FastAPI dependencies.

This module defines the seams for authentication and service wiring. The concrete
Cognito JWT validation is implemented in task group 4; here we establish the
dependency interface so routers can declare an authenticated-user requirement and
never trust a client-supplied ``user_id`` (see security steering).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.core.config import Settings, get_settings
from src.core.errors import UnauthorizedError

# auto_error=False so we can raise our own consistent error envelope.
_bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """The authenticated identity derived from a validated Cognito JWT.

    ``user_id`` is the trusted subject used for all server-side ownership checks.
    """

    user_id: str
    email: str | None = None


SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    settings: SettingsDep,
) -> AuthenticatedUser:
    """Resolve the authenticated user from the bearer token.

    Interface only: real Cognito JWT verification (signature, issuer, audience,
    expiry) is implemented in the authentication task group. Until then this
    dependency enforces the presence of a bearer token so protected routes fail
    closed rather than open.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("A bearer token is required")

    # TODO(auth): validate the JWT against the Cognito JWKS and derive claims.
    raise UnauthorizedError("Authentication is not yet configured")


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
