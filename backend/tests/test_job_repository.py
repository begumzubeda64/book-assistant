"""Tests for the DynamoDB job repository against an in-memory fake table."""

from __future__ import annotations

from typing import Any

import pytest
from src.models.job import Job, JobStatus, JobType
from src.repositories.jobs import DynamoDBJobRepository


class FakeTable:
    """Minimal in-memory stand-in for a boto3 DynamoDB Table."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def put_item(self, Item: dict[str, Any], ConditionExpression: str | None = None):  # noqa: N803
        if ConditionExpression and Item["job_id"] in self.items:
            raise AssertionError("condition failed")
        self.items[Item["job_id"]] = Item

    def get_item(self, Key: dict[str, Any]):  # noqa: N803
        item = self.items.get(Key["job_id"])
        return {"Item": item} if item else {}

    def query(self, **kwargs: Any):
        key = kwargs["ExpressionAttributeValues"][":k"]
        matches = [
            i for i in self.items.values() if i.get("idempotency_key") == key
        ]
        return {"Items": matches[:1]}

    def update_item(self, **kwargs: Any):
        job_id = kwargs["Key"]["job_id"]
        values = kwargs["ExpressionAttributeValues"]
        item = self.items[job_id]
        item["status"] = values[":s"]
        if ":p" in values:
            item["progress"] = values[":p"]
        if ":r" in values:
            item["result_location"] = values[":r"]
        if ":e" in values:
            item["error_code"] = values[":e"]


def _job(**kw: Any) -> Job:
    base = {
        "job_id": "j1",
        "user_id": "u1",
        "job_type": JobType.BOOK_INGESTION,
    }
    base.update(kw)
    return Job(**base)


@pytest.mark.asyncio
async def test_create_and_get() -> None:
    repo = DynamoDBJobRepository(FakeTable())
    await repo.create(_job())
    fetched = await repo.get("j1")
    assert fetched is not None
    assert fetched.user_id == "u1"
    assert fetched.status is JobStatus.QUEUED


@pytest.mark.asyncio
async def test_create_is_idempotent_on_key() -> None:
    repo = DynamoDBJobRepository(FakeTable())
    first = await repo.create(_job(job_id="a", idempotency_key="dup"))
    second = await repo.create(_job(job_id="b", idempotency_key="dup"))
    assert first.job_id == second.job_id == "a"


@pytest.mark.asyncio
async def test_update_status() -> None:
    repo = DynamoDBJobRepository(FakeTable())
    await repo.create(_job())
    await repo.update_status(
        "j1", JobStatus.COMPLETED, result_location="s3://x/y"
    )
    fetched = await repo.get("j1")
    assert fetched is not None
    assert fetched.status is JobStatus.COMPLETED
    assert fetched.result_location == "s3://x/y"


@pytest.mark.asyncio
async def test_get_missing_returns_none() -> None:
    repo = DynamoDBJobRepository(FakeTable())
    assert await repo.get("nope") is None
