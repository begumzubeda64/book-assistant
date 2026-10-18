"""Reading progress service.

Progress is always scoped to the authenticated user: reads and writes use the
token-derived ``user_id`` as the partition key, so a user can only ever access
their own progress (requirement 1.3). The service never accepts a client-supplied
user id.
"""

from __future__ import annotations

from src.models.progress import Progress
from src.repositories.progress import ProgressRepository
from src.schemas.progress import ProgressUpdate


class ProgressService:
    def __init__(self, *, repository: ProgressRepository) -> None:
        self._repo = repository

    async def get_progress(self, user_id: str, book_id: str) -> Progress | None:
        """Return saved progress for the user's book (continue-reading entry)."""
        return await self._repo.get(user_id, book_id)

    async def save_progress(
        self, user_id: str, book_id: str, update: ProgressUpdate
    ) -> Progress:
        """Idempotently upsert the user's progress for a book."""
        progress = Progress(
            user_id=user_id,
            book_id=book_id,
            chapter_id=update.chapter_id,
            position=update.position,
            selected_duration=update.selected_duration,
            selected_mode=update.selected_mode,
            completed=update.completed,
        )
        return await self._repo.save(progress)
