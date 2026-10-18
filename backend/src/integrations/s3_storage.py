"""S3 storage integration.

Generates short-lived presigned PUT URLs so the browser uploads the PDF directly
to a private bucket; the PDF never travels through FastAPI (requirement 3.2).
Object keys are namespaced per user so ownership can be validated server-side by
key prefix (security steering).
"""

from __future__ import annotations

from typing import Any, Protocol

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def build_upload_key(user_id: str, book_id: str) -> str:
    """Deterministic private key for a user's uploaded book."""
    return f"uploads/{user_id}/{book_id}.pdf"


def owns_key(user_id: str, object_key: str) -> bool:
    """True if the key is within the user's private upload prefix."""
    return object_key.startswith(f"uploads/{user_id}/")


class StoragePort(Protocol):
    def presign_put(
        self, object_key: str, *, content_type: str, expires_in: int
    ) -> str: ...

    def object_exists(self, object_key: str) -> bool: ...


class S3Storage:
    """S3-backed storage. The boto3 client is injected for testability."""

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings, bucket: str) -> S3Storage:
        import boto3

        client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        )
        return cls(client, bucket)

    def presign_put(
        self, object_key: str, *, content_type: str, expires_in: int
    ) -> str:
        url: str = self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url

    def object_exists(self, object_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=object_key)
            return True
        except Exception:
            return False
