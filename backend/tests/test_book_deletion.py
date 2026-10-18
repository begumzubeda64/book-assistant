"""Tests for book deletion: removes a user's content, preserves audit trail."""

from __future__ import annotations

import io
import json
from typing import Any

from src.services.book_deletion import BookDeletionService


class FakeS3:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = dict(objects or {})
        self.deleted: list[str] = []

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop(Key, None)
        self.deleted.append(Key)

    def get_object(self, Bucket: str, Key: str):  # noqa: N803
        return {"Body": io.BytesIO(self.objects[Key])}

    def get_paginator(self, _name: str):
        objects = self.objects

        class _Paginator:
            def paginate(self, Bucket: str, Prefix: str):  # noqa: N803
                yield {
                    "Contents": [
                        {"Key": k} for k in objects if k.startswith(Prefix)
                    ]
                }

        return _Paginator()


class FakeTable:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items = list(items or [])
        self.deleted_keys: list[dict[str, Any]] = []

    def query(self, **_kwargs: Any) -> dict[str, Any]:
        return {"Items": self.items}

    def delete_item(self, Key: dict[str, Any]) -> None:  # noqa: N803
        self.deleted_keys.append(Key)


class FakeKbDeleter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def delete_book(self, *, user_id: str, book_id: str) -> int:
        self.calls.append((user_id, book_id))
        return 3


def _reading(user: str, rid: str, book: str) -> tuple[str, bytes]:
    return (
        f"readings/{user}/{rid}.json",
        json.dumps({"reading_id": rid, "book_id": book}).encode(),
    )


def _service(s3: FakeS3, convs: FakeTable, prog: FakeTable, kb: FakeKbDeleter):
    return BookDeletionService(
        s3_client=s3,
        uploads_bucket="uploads",
        reading_results_bucket="readings",
        conversations_table=convs,
        progress_table=prog,
        kb_deleter=kb,
    )


def test_deletes_all_content_for_the_book() -> None:
    user, book = "u1", "b1"
    k1, v1 = _reading(user, "r1", book)
    k2, v2 = _reading(user, "r2", "other-book")
    s3 = FakeS3(
        {
            f"uploads/{user}/{book}.pdf": b"%PDF",
            k1: v1,
            k2: v2,
        }
    )
    convs = FakeTable(
        [
            {"conversation_id": "c1", "book_id": book},
            {"conversation_id": "c2", "book_id": "other-book"},
        ]
    )
    prog = FakeTable()
    kb = FakeKbDeleter()

    summary = _service(s3, convs, prog, kb).delete_book(user_id=user, book_id=book)

    # PDF deleted
    assert f"uploads/{user}/{book}.pdf" in s3.deleted
    assert summary["deleted_pdf"] is True
    # KB delete called with the scoped user
    assert kb.calls == [(user, book)]
    assert summary["deleted_chunks"] == 3
    # Only this book's reading deleted, not the other book's
    assert k1 in s3.deleted and k2 not in s3.deleted
    assert summary["deleted_readings"] == 1
    # Only this book's conversation deleted
    assert convs.deleted_keys == [{"user_id": user, "conversation_id": "c1"}]
    assert summary["deleted_conversations"] == 1
    # Progress deleted
    assert prog.deleted_keys == [{"user_id": user, "book_id": book}]
    assert summary["deleted_progress"] is True


def test_deletion_is_scoped_to_the_requesting_user() -> None:
    # Only the caller's own prefixes/partitions are ever touched: the KB deleter
    # receives the caller's user_id, and S3/Dynamo keys are built from it.
    s3 = FakeS3({"uploads/u1/b1.pdf": b"%PDF"})
    kb = FakeKbDeleter()
    _service(s3, FakeTable(), FakeTable(), kb).delete_book(
        user_id="u1", book_id="b1"
    )
    assert kb.calls == [("u1", "b1")]
    # No other user's key could be constructed or deleted.
    assert all(
        k.startswith("uploads/u1/") or k.startswith("readings/u1/")
        for k in s3.deleted
    )


def test_idempotent_when_nothing_exists() -> None:
    # Deleting an absent book succeeds with zero/false counts (no raise).
    summary = _service(FakeS3(), FakeTable(), FakeTable(), FakeKbDeleter()).delete_book(
        user_id="u1", book_id="missing"
    )
    assert summary["deleted_readings"] == 0
    assert summary["deleted_conversations"] == 0
