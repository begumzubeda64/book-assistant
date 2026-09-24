"""Tests for Cognito JWT validation.

A local RSA keypair mints tokens and a fake signing-key client returns the
public key, so the validator is exercised without a live Cognito user pool.
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from src.core.errors import UnauthorizedError
from src.core.security.cognito import CognitoJwtValidator

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TESTPOOL"
CLIENT_ID = "test-client-id"


class _Key:
    def __init__(self, key: Any) -> None:
        self.key = key


class FakeSigningKeyClient:
    """Returns a fixed public key regardless of the token's kid."""

    def __init__(self, public_key: Any) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> _Key:  # noqa: ARG002
        return _Key(self._public_key)


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def validator(rsa_keypair: tuple[Any, Any]) -> CognitoJwtValidator:
    _, public_key = rsa_keypair
    return CognitoJwtValidator(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        signing_key_client=FakeSigningKeyClient(public_key),
    )


def _mint(private_key: Any, **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user-123",
        "iss": ISSUER,
        "token_use": "access",
        "client_id": CLIENT_ID,
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_valid_access_token(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    token = _mint(private_key, email="reader@example.com")
    user = validator.validate(token)
    assert user.user_id == "user-123"
    assert user.email == "reader@example.com"


def test_valid_id_token(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    token = _mint(private_key, token_use="id", aud=CLIENT_ID, client_id=None)
    user = validator.validate(token)
    assert user.user_id == "user-123"


def test_expired_token_rejected(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    now = int(time.time())
    token = _mint(private_key, iat=now - 7200, exp=now - 3600)
    with pytest.raises(UnauthorizedError):
        validator.validate(token)


def test_wrong_issuer_rejected(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    token = _mint(private_key, iss="https://evil.example.com/pool")
    with pytest.raises(UnauthorizedError):
        validator.validate(token)


def test_wrong_access_client_id_rejected(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    token = _mint(private_key, client_id="some-other-client")
    with pytest.raises(UnauthorizedError):
        validator.validate(token)


def test_wrong_id_audience_rejected(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    token = _mint(private_key, token_use="id", aud="other-client", client_id=None)
    with pytest.raises(UnauthorizedError):
        validator.validate(token)


def test_unexpected_token_use_rejected(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    token = _mint(private_key, token_use="refresh")
    with pytest.raises(UnauthorizedError):
        validator.validate(token)


def test_bad_signature_rejected(validator: CognitoJwtValidator) -> None:
    # Token signed by a different, unrelated key.
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _mint(other_key)
    with pytest.raises(UnauthorizedError):
        validator.validate(token)


def test_missing_subject_rejected(
    validator: CognitoJwtValidator, rsa_keypair: tuple[Any, Any]
) -> None:
    private_key, _ = rsa_keypair
    # 'require' includes 'sub', so PyJWT rejects a missing subject.
    token = _mint(private_key, sub=None)
    with pytest.raises(UnauthorizedError):
        validator.validate(token)
