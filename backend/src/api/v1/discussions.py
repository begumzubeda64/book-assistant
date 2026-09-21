"""GraphRAG discussion endpoints.

    POST /api/v1/discussions
    POST /api/v1/discussions/{conversation_id}/messages
    GET  /api/v1/discussions/{conversation_id}

Implemented in task group 9 (discussion assistant).
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/discussions", tags=["discussions"])


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_discussion() -> dict[str, str]:
    """Start a discussion conversation for a book (not yet implemented)."""
    return {"detail": "not_implemented"}


@router.post(
    "/{conversation_id}/messages", status_code=status.HTTP_501_NOT_IMPLEMENTED
)
async def post_message(conversation_id: str) -> dict[str, str]:
    """Ask a question in a conversation (not yet implemented)."""
    return {"detail": "not_implemented"}


@router.get("/{conversation_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_discussion(conversation_id: str) -> dict[str, str]:
    """Fetch a conversation and its messages (not yet implemented)."""
    return {"detail": "not_implemented"}
