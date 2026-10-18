"""Tests for signed per-job scope tokens."""

from __future__ import annotations

import pytest
from src.mcp_server.scope import (
    ScopeError,
    mint_scope_token,
    verify_scope_token,
)

_SECRET = "unit-test-secret"


def test_mint_and_verify_roundtrip() -> None:
    token = mint_scope_token(user_id="u1", job_id="j1", secret=_SECRET, now=1000)
    scope = verify_scope_token(token, secret=_SECRET, now=1001)
    assert scope.user_id == "u1"
    assert scope.job_id == "j1"
    assert scope.expires_at == 1000 + 900


def test_expired_token_is_rejected() -> None:
    token = mint_scope_token(
        user_id="u1", job_id="j1", secret=_SECRET, ttl_seconds=10, now=1000
    )
    with pytest.raises(ScopeError):
        verify_scope_token(token, secret=_SECRET, now=1011)


def test_tampered_payload_is_rejected() -> None:
    token = mint_scope_token(user_id="u1", job_id="j1", secret=_SECRET)
    payload_b64, sig = token.split(".", 1)
    # Flip the payload to impersonate another user; signature no longer matches.
    forged = mint_scope_token(user_id="attacker", job_id="j1", secret="other")
    forged_payload = forged.split(".", 1)[0]
    with pytest.raises(ScopeError):
        verify_scope_token(f"{forged_payload}.{sig}", secret=_SECRET)


def test_wrong_secret_is_rejected() -> None:
    token = mint_scope_token(user_id="u1", job_id="j1", secret=_SECRET)
    with pytest.raises(ScopeError):
        verify_scope_token(token, secret="different-secret")


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(ScopeError):
        verify_scope_token("not-a-token", secret=_SECRET)


def test_empty_token_is_rejected() -> None:
    with pytest.raises(ScopeError):
        verify_scope_token("", secret=_SECRET)
