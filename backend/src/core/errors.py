"""Application error types and consistent error responses.

The API returns a predictable JSON error structure (see design.md, "Error
Handling"):

    {"error": {"code": "...", "message": "...", "request_id": "..."}}

Internal stack traces, AWS request details, and secrets are never exposed.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.logging import get_logger

logger = get_logger(__name__)

# Version-agnostic literal: Starlette renamed the 422 constant across releases.
HTTP_422_UNPROCESSABLE = 422


class AppError(Exception):
    """Base application error carrying a stable machine-readable code."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "The requested resource could not be found"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"
    message = "Authentication is required"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "You do not have access to this resource"


class ValidationAppError(AppError):
    status_code = HTTP_422_UNPROCESSABLE
    code = "VALIDATION_ERROR"
    message = "The request was invalid"


def _error_body(code: str, message: str, request_id: str | None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach centralized exception handlers to the FastAPI app."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.info(
            "application_error",
            extra={
                "request_id": request_id,
                "error_code": exc.code,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE,
            content=_error_body(
                "VALIDATION_ERROR", "The request was invalid", request_id
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        code = "HTTP_ERROR"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code = "FORBIDDEN"
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, message, request_id),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        # Do not leak the exception detail to the client.
        logger.error(
            "unhandled_error",
            extra={"request_id": request_id, "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_ERROR", "An unexpected error occurred", request_id
            ),
        )
