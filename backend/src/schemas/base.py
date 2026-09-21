"""Base Pydantic schemas shared across the API."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    """Base model for all API schemas."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorDetail(APIModel):
    """Machine-readable error detail."""

    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    request_id: str | None = Field(
        default=None, description="Correlation ID for tracing"
    )


class ErrorResponse(APIModel):
    """Consistent error envelope returned by the API."""

    error: ErrorDetail


class Page(APIModel, Generic[T]):
    """Generic pagination envelope for list endpoints."""

    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = Field(
        default=None, description="Opaque cursor for the next page, if any"
    )
