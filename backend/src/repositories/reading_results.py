"""Reading-result reader.

Reads generated adaptive-reading results back from S3 for the API. Results are
written by the adaptive-reading agent under a per-user prefix; reads are scoped
to the authenticated user's prefix so a user can only fetch their own readings.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class ReadingResultRepository(Protocol):
    async def get(self, user_id: str, reading_id: str) -> dict[str, Any] | None: ...


class S3ReadingResultRepository:
    def __init__(self, s3_client: Any, bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = bucket

    @classmethod
    def from_settings(
        cls, settings: Settings, bucket: str
    ) -> S3ReadingResultRepository:
        import boto3

        client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        )
        return cls(client, bucket)

    async def get(self, user_id: str, reading_id: str) -> dict[str, Any] | None:
        key = f"readings/{user_id}/{reading_id}.json"
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            logger.info(
                "reading_result_get_failed",
                extra={"error_type": type(exc).__name__},
            )
            return None
        payload: dict[str, Any] = json.loads(response["Body"].read())
        return payload
