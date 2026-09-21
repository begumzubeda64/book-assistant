"""Aggregate router for API v1.

Collects the per-domain routers (books, uploads, reading, discussions,
recommendations, jobs, progress) into a single router mounted under
``/api/v1``.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import (
    books,
    discussions,
    jobs,
    progress,
    reading,
    recommendations,
    uploads,
)

api_router = APIRouter()
api_router.include_router(books.router)
api_router.include_router(uploads.router)
api_router.include_router(reading.router)
api_router.include_router(discussions.router)
api_router.include_router(recommendations.router)
api_router.include_router(jobs.router)
api_router.include_router(progress.router)
