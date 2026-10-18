"""Health check schema."""

from __future__ import annotations

from src.schemas.base import APIModel


class HealthResponse(APIModel):
    """Response for the load-balancer health check."""

    status: str = "ok"
    service: str
    environment: str
