"""Signed per-invocation scope tokens.

The trusted ``user_id`` for a job originates from the authenticated API (the
Cognito ``sub`` on the DynamoDB job record) and flows API -> SQS -> dispatcher
-> agent -> MCP tool server. To stop a *compromised agent process* from passing
an arbitrary ``user_id`` to a tool, the dispatcher mints a short-lived
HMAC-signed scope token binding ``user_id`` (and ``job_id``) with an expiry. The
MCP server verifies the token and derives ``user_id`` from it, ignoring any
``user_id`` a caller puts in tool arguments.

The signing secret is shared only by the dispatcher (minting) and the MCP server
(verifying) via Secrets Manager; the agent roles never hold it, so a breached
agent cannot forge a token for a different user.

Token format (URL-safe, compact):  base64url(payload_json) + "." + base64url(hmac)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

# Default token lifetime. Long enough to cover a multi-step agent run, short
# enough that a leaked token is quickly useless.
DEFAULT_TTL_SECONDS = 900


class ScopeError(Exception):
    """Raised when a scope token is missing, malformed, forged, or expired."""


@dataclass(frozen=True)
class JobScope:
    """The verified, trusted scope for one agent invocation."""

    user_id: str
    job_id: str
    expires_at: int


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64url_encode(digest)


def mint_scope_token(
    *,
    user_id: str,
    job_id: str,
    secret: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> str:
    """Create a signed scope token binding user_id + job_id with an expiry."""
    if not user_id:
        raise ScopeError("user_id is required to mint a scope token")
    if not secret:
        raise ScopeError("A signing secret is required to mint a scope token")
    issued = int(now if now is not None else time.time())
    payload = {
        "user_id": user_id,
        "job_id": job_id,
        "exp": issued + ttl_seconds,
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature}"


def verify_scope_token(
    token: str, *, secret: str, now: int | None = None
) -> JobScope:
    """Verify a scope token and return the trusted JobScope.

    Raises ScopeError on any tampering, bad signature, or expiry. Uses a
    constant-time signature comparison.
    """
    if not token:
        raise ScopeError("Missing scope token")
    if not secret:
        raise ScopeError("A signing secret is required to verify a scope token")

    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise ScopeError("Malformed scope token") from exc

    expected = _sign(payload_b64, secret)
    if not hmac.compare_digest(expected, signature):
        raise ScopeError("Invalid scope token signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ScopeError("Malformed scope token payload") from exc

    user_id = payload.get("user_id")
    exp = payload.get("exp")
    if not user_id or not isinstance(exp, int):
        raise ScopeError("Scope token is missing required claims")

    current = int(now if now is not None else time.time())
    if current >= exp:
        raise ScopeError("Scope token has expired")

    return JobScope(
        user_id=user_id, job_id=payload.get("job_id", ""), expires_at=exp
    )
