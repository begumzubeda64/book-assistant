"""FastAPI application entry point.

Wires configuration, structured logging, request-context middleware, centralized
error handling, CORS, the health check, and the versioned API router. The same
application runs locally and in the ECS container (requirement 10.1).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.core.config import Settings, get_settings
from src.core.errors import register_exception_handlers
from src.core.logging import configure_logging
from src.core.middleware import RequestContextMiddleware
from src.schemas.health import HealthResponse

OPENAPI_TAGS = [
    {"name": "books", "description": "Book discovery and metadata."},
    {"name": "uploads", "description": "Authorized PDF upload and ingestion."},
    {"name": "reading", "description": "Adaptive reading generation."},
    {"name": "discussions", "description": "GraphRAG-grounded discussion."},
    {"name": "recommendations", "description": "Book recommendations."},
    {"name": "jobs", "description": "Asynchronous job status."},
    {"name": "progress", "description": "Reading progress."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/health", tags=["health"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Load-balancer health check."""
        return HealthResponse(service=settings.app_name, environment=settings.app_env)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
