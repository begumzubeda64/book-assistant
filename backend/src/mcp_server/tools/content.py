"""Content-access tool (MCP).

Fetches authorized uploaded PDF bytes from S3. Re-checks that the object key
belongs to the requesting user's private prefix; the tool never trusts the
caller to have already authorized the request (security.md).
"""

from __future__ import annotations

from typing import Any

from src.core.errors import ForbiddenError
from src.integrations.s3_storage import owns_key


class ContentTool:
    """Authorized content access backed by S3."""

    def __init__(self, s3_client: Any, bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = bucket

    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:
        # Re-enforce ownership at the tool boundary.
        if not owns_key(user_id, object_key):
            raise ForbiddenError("Not authorized to access this object")
        response = self._s3.get_object(Bucket=self._bucket, Key=object_key)
        body: bytes = response["Body"].read()
        return body
