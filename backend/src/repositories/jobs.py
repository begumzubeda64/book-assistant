"""Job repository (DynamoDB).

Persists jobs and their status transitions. Create is idempotent on
``idempotency_key`` so retried job-creation requests do not produce duplicate
expensive work (requirement 8.3, design.md job idempotency).

The boto3 table resource is injected so tests use a fake and local runs use
DynamoDB Local without real AWS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from botocore.exceptions import ClientError

from src.core.logging import get_logger
from src.models.job import Job, JobStatus

logger = get_logger(__name__)


class JobRepository(Protocol):
    async def create(self, job: Job) -> Job: ...

    async def get(self, job_id: str) -> Job | None: ...

    async def find_by_idempotency_key(self, key: str) -> Job | None: ...

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: int | None = None,
        result_location: str | None = None,
        error_code: str | None = None,
    ) -> None: ...


class DynamoDBJobRepository:
    """DynamoDB-backed job repository.

    Table design: partition key ``job_id``; a global secondary index
    ``idempotency-index`` on ``idempotency_key`` supports idempotent create.
    """

    IDEMPOTENCY_INDEX = "idempotency-index"

    def __init__(self, table: Any) -> None:
        self._table = table

    async def create(self, job: Job) -> Job:
        if job.idempotency_key:
            existing = await self.find_by_idempotency_key(job.idempotency_key)
            if existing is not None:
                return existing
        self._table.put_item(
            Item=self._to_item(job),
            ConditionExpression="attribute_not_exists(job_id)",
        )
        return job

    async def get(self, job_id: str) -> Job | None:
        response = self._table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        return self._from_item(item) if item else None

    async def find_by_idempotency_key(self, key: str) -> Job | None:
        response = self._table.query(
            IndexName=self.IDEMPOTENCY_INDEX,
            KeyConditionExpression="idempotency_key = :k",
            ExpressionAttributeValues={":k": key},
            Limit=1,
        )
        items = response.get("Items") or []
        return self._from_item(items[0]) if items else None

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: int | None = None,
        result_location: str | None = None,
        error_code: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        expr = ["#s = :s", "updated_at = :u"]
        names: dict[str, str] = {"#s": "status"}
        values: dict[str, Any] = {":s": status.value, ":u": now}
        if progress is not None:
            expr.append("progress = :p")
            values[":p"] = progress
        if result_location is not None:
            expr.append("result_location = :r")
            values[":r"] = result_location
        if error_code is not None:
            expr.append("error_code = :e")
            values[":e"] = error_code
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            expr.append("completed_at = :c")
            values[":c"] = now
        try:
            self._table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET " + ", ".join(expr),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
        except ClientError as exc:
            logger.info(
                "job_update_failed",
                extra={"job_id": job_id, "error_type": type(exc).__name__},
            )
            raise

    @staticmethod
    def _to_item(job: Job) -> dict[str, Any]:
        item = job.model_dump(mode="json", exclude_none=True)
        return item

    @staticmethod
    def _from_item(item: dict[str, Any]) -> Job:
        return Job.model_validate(item)
