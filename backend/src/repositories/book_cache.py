"""DynamoDB cache for normalized book metadata.

Opportunistic cache: reads and writes degrade gracefully. A cache miss or any
DynamoDB error must never fail a discovery request — the service simply falls
back to the live providers. This keeps discovery working locally without a
configured table.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.core.config import Settings
from src.core.logging import get_logger
from src.schemas.books import BookMetadata

logger = get_logger(__name__)


class BookCacheRepository(Protocol):
    """Persistence interface for cached book metadata."""

    async def get(self, book_id: str) -> BookMetadata | None: ...

    async def put(self, book: BookMetadata) -> None: ...


class DynamoDBBookCache:
    """DynamoDB-backed book metadata cache.

    The boto3 table resource is injected so tests can supply a fake and so the
    local endpoint (DynamoDB Local) can be used without real AWS.
    """

    def __init__(self, table: Any) -> None:
        self._table = table

    @classmethod
    def from_settings(cls, settings: Settings, table_name: str) -> DynamoDBBookCache:
        import boto3

        resource = boto3.resource(
            "dynamodb",
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
        )
        return cls(resource.Table(table_name))

    async def get(self, book_id: str) -> BookMetadata | None:
        try:
            response = self._table.get_item(Key={"book_id": book_id})
        except Exception as exc:  # never fail discovery on cache errors
            logger.info(
                "book_cache_get_failed",
                extra={"error_type": type(exc).__name__},
            )
            return None
        item = response.get("Item")
        if not item or "payload" not in item:
            return None
        try:
            return BookMetadata.model_validate(json.loads(item["payload"]))
        except Exception:
            return None

    async def put(self, book: BookMetadata) -> None:
        try:
            self._table.put_item(
                Item={
                    "book_id": book.book_id,
                    "payload": book.model_dump_json(),
                }
            )
        except Exception as exc:  # never fail discovery on cache errors
            logger.info(
                "book_cache_put_failed",
                extra={"error_type": type(exc).__name__},
            )


class NullBookCache:
    """No-op cache used when no DynamoDB table is configured (local default)."""

    async def get(self, book_id: str) -> BookMetadata | None:
        return None

    async def put(self, book: BookMetadata) -> None:
        return None
