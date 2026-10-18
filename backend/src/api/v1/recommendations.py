"""Recommendation endpoints.

    GET /api/v1/recommendations

Returns transparently scored book recommendations for the authenticated user,
each with a concise reason. Scoring is a documented, testable formula (no learned
model); see services/recommendation_scoring.py.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from src.api.dependencies import CurrentUser, RecommendationServiceDep
from src.schemas.recommendations import RecommendationsResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponse)
async def get_recommendations(
    user: CurrentUser,
    service: RecommendationServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RecommendationsResponse:
    """Return recommended books with reasons for the authenticated user."""
    items = await service.recommend(user.user_id, limit=limit)
    return RecommendationsResponse(items=items)
