"""Progress repository (DynamoDB).

Table design: partition key ``user_id``, sort key ``book_id``. A user's progress
for a book is a single item, so ``put`` is a natural idempotent upsert.

The boto3 table resource is injected so tests use a fake and local runs use
DynamoDB Local without real AWS.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.models.progress import Progress


class ProgressRepository(Protocol):
    async def get(self, user_id: str, book_id: str) -> Progress | None: ...

    async def save(self, progress: Progress) -> Progress: ...


class DynamoDBProgressRepository:
    def __init__(self, table: Any) -> None:
        self._table = table

    async def get(self, user_id: str, book_id: str) -> Progress | None:
        response = self._table.get_item(
            Key={"user_id": user_id, "book_id": book_id}
        )
        item = response.get("Item")
        return Progress.model_validate(item) if item else None

    async def save(self, progress: Progress) -> Progress:
        # Single item per (user, book): put is an idempotent upsert.
        self._table.put_item(
            Item=progress.model_dump(mode="json", exclude_none=True)
        )
        return progress
