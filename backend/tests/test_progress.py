"""Tests for the progress repository and service."""

from __future__ import annotations

from typing import Any

import pytest
from src.models.reading import ReadingMode
from src.repositories.progress import DynamoDBProgressRepository
from src.schemas.progress import ProgressUpdate
from src.services.progress import ProgressService


class FakeProgressTable:
    """In-memory stand-in for a boto3 DynamoDB Table (PK user_id, SK book_id)."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def get_item(self, Key: dict[str, Any]):  # noqa: N803
        item = self.items.get((Key["user_id"], Key["book_id"]))
        return {"Item": item} if item else {}

    def put_item(self, Item: dict[str, Any]):  # noqa: N803
        self.items[(Item["user_id"], Item["book_id"])] = Item


@pytest.mark.asyncio
async def test_repo_save_then_get_roundtrip() -> None:
    repo = DynamoDBProgressRepository(FakeProgressTable())
    service = ProgressService(repository=repo)

    saved = await service.save_progress(
        "u1",
        "book1",
        ProgressUpdate(
            chapter_id="ch2",
            position=1200,
            selected_duration=5,
            selected_mode=ReadingMode.BALANCED_READ,
        ),
    )
    assert saved.user_id == "u1"

    fetched = await service.get_progress("u1", "book1")
    assert fetched is not None
    assert fetched.chapter_id == "ch2"
    assert fetched.position == 1200
    assert fetched.selected_mode is ReadingMode.BALANCED_READ
    assert fetched.completed is False


@pytest.mark.asyncio
async def test_save_is_idempotent_upsert() -> None:
    repo = DynamoDBProgressRepository(FakeProgressTable())
    service = ProgressService(repository=repo)

    await service.save_progress("u1", "book1", ProgressUpdate(position=100))
    await service.save_progress("u1", "book1", ProgressUpdate(position=300))

    fetched = await service.get_progress("u1", "book1")
    assert fetched is not None
    assert fetched.position == 300  # last write wins, single item


@pytest.mark.asyncio
async def test_completion_state() -> None:
    repo = DynamoDBProgressRepository(FakeProgressTable())
    service = ProgressService(repository=repo)
    await service.save_progress(
        "u1", "book1", ProgressUpdate(position=9999, completed=True)
    )
    fetched = await service.get_progress("u1", "book1")
    assert fetched is not None
    assert fetched.completed is True


@pytest.mark.asyncio
async def test_progress_is_partitioned_per_user() -> None:
    table = FakeProgressTable()
    service = ProgressService(repository=DynamoDBProgressRepository(table))
    await service.save_progress("u1", "book1", ProgressUpdate(position=10))
    await service.save_progress("u2", "book1", ProgressUpdate(position=20))

    p1 = await service.get_progress("u1", "book1")
    p2 = await service.get_progress("u2", "book1")
    assert p1 is not None and p1.position == 10
    assert p2 is not None and p2.position == 20


@pytest.mark.asyncio
async def test_get_missing_returns_none() -> None:
    service = ProgressService(
        repository=DynamoDBProgressRepository(FakeProgressTable())
    )
    assert await service.get_progress("u1", "unknown") is None
