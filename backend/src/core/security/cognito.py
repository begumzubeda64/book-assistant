"""Cognito JWT validation.

Verifies a Cognito-issued JWT (RS256) against the user pool's JWKS and derives
the trusted ``user_id`` used for all server-side ownership checks. Never trusts a
client-supplied user identity.

Validation performed:
- signature (RS256) against the pool's JWKS (keyed by ``kid``)
- ``exp`` / ``nbf`` / ``iat`` expiry
- ``iss`` equals the configured user pool issuer
- ``token_use`` is one of the accepted uses (``access`` or ``id``)
- audience:
    * for ``id`` tokens, ``aud`` equals the app client id
    * for ``access`` tokens, ``client_id`` claim equals the app client id
      (access tokens have no ``aud``)

The JWKS client is injectable so tests can supply a local signing key without a
live Cognito user pool.
"""

from __future__ import annotations

from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel

from src.core.config import Settings
from src.core.errors import UnauthorizedError
from src.core.logging import get_logger

logger = get_logger(__name__)

_ACCEPTED_TOKEN_USES = frozenset({"access", "id"})
_ALGORITHMS = ["RS256"]


class AuthenticatedUser(BaseModel):
    """The authenticated identity derived from a validated Cognito JWT.

    ``user_id`` is the trusted subject (``sub``) used for all ownership checks.
    """

    user_id: str
    email: str | None = None


class SigningKeyClient(Protocol):
    """Minimal interface for resolving a JWT's signing key from its header."""

    def get_signing_key_from_jwt(self, token: str) -> Any:  # pragma: no cover
        ...


class CognitoJwtValidator:
    """Validate Cognito JWTs and map claims to an AuthenticatedUser."""

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        signing_key_client: SigningKeyClient,
    ) -> None:
        self._issuer = issuer
        self._client_id = client_id
        self._keys = signing_key_client

    @classmethod
    def from_settings(cls, settings: Settings) -> CognitoJwtValidator:
        """Build a validator from application settings.

        Raises UnauthorizedError if Cognito is not configured, so protected
        routes fail closed rather than open.
        """
        if not settings.cognito_issuer or not settings.cognito_client_id:
            raise UnauthorizedError("Authentication is not configured")
        jwks_url = settings.cognito_jwks_url
        assert jwks_url is not None  # implied by cognito_issuer being set
        return cls(
            issuer=settings.cognito_issuer,
            client_id=settings.cognito_client_id,
            signing_key_client=PyJWKClient(jwks_url),
        )

    def validate(self, token: str) -> AuthenticatedUser:
        """Validate a raw bearer token and return the authenticated user."""
        try:
            signing_key = self._keys.get_signing_key_from_jwt(token)
        except Exception as exc:  # key resolution / JWKS failure
            logger.info(
                "jwt_key_resolution_failed",
                extra={"error_type": type(exc).__name__},
            )
            raise UnauthorizedError("Invalid authentication token") from exc

        # Decode without audience verification here; audience differs by
        # token_use (id -> aud, access -> client_id), handled explicitly below.
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=_ALGORITHMS,
                issuer=self._issuer,
                options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            logger.info("jwt_decode_failed", extra={"error_type": type(exc).__name__})
            raise UnauthorizedError("Invalid authentication token") from exc

        self._verify_token_use_and_audience(claims)

        user_id = claims.get("sub")
        if not user_id:
            raise UnauthorizedError("Token is missing a subject")

        return AuthenticatedUser(user_id=user_id, email=claims.get("email"))

    def _verify_token_use_and_audience(self, claims: dict[str, Any]) -> None:
        token_use = claims.get("token_use")
        if token_use not in _ACCEPTED_TOKEN_USES:
            raise UnauthorizedError("Unexpected token use")

        if token_use == "id":
            if claims.get("aud") != self._client_id:
                raise UnauthorizedError("Token audience mismatch")
        else:  # access token
            if claims.get("client_id") != self._client_id:
                raise UnauthorizedError("Token client mismatch")
