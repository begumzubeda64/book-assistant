"""SQS integration.

Enqueues job trigger messages. SQS plus the DynamoDB job record are the durable
async boundary between the application tier and the agent tier (design.md,
tech.md). The client is injected for testability; local runs use LocalStack.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class QueuePort(Protocol):
    def send_job(self, message: dict[str, Any], *, dedup_id: str | None = None) -> None:
        ...


class SqsQueue:
    """SQS-backed job queue. The boto3 client is injected for testability."""

    def __init__(self, client: Any, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    @classmethod
    def from_settings(cls, settings: Settings, queue_url: str) -> SqsQueue:
        import boto3

        client = boto3.client(
            "sqs",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        )
        return cls(client, queue_url)

    def send_job(
        self, message: dict[str, Any], *, dedup_id: str | None = None
    ) -> None:
        kwargs: dict[str, Any] = {
            "QueueUrl": self._queue_url,
            "MessageBody": json.dumps(message),
        }
        # FIFO queues use dedup ids; standard queues ignore this kwarg.
        if dedup_id and self._queue_url.endswith(".fifo"):
            kwargs["MessageDeduplicationId"] = dedup_id
            kwargs["MessageGroupId"] = message.get("job_type", "default")
        self._client.send_message(**kwargs)


class NullQueue:
    """No-op queue for local runs without SQS configured."""

    def send_job(
        self, message: dict[str, Any], *, dedup_id: str | None = None
    ) -> None:
        logger.info(
            "job_enqueue_skipped_no_queue",
            extra={"job_type": message.get("job_type")},
        )
