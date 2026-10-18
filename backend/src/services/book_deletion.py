"""Book deletion service.

Removes all of a user's content for one book while preserving the audit trail:
job records and CloudWatch logs are never touched. Deletes:
  - the uploaded PDF (uploads bucket)
  - prepared chunks + KB/GraphRAG data (via the MCP tool tier)
  - adaptive-reading results for the book (reading-results bucket)
  - conversations about the book (conversations table)
  - reading progress for the book (progress table)

Ownership is enforced implicitly: every store is addressed by the authenticated
``user_id``'s own key prefix / partition, so a user can only delete their own
content. The deletion itself is audit-logged (``book_deleted``) with safe
identifiers and counts only.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.core.logging import get_logger
from src.integrations.s3_storage import build_upload_key

logger = get_logger(__name__)


class KnowledgeBaseDeleter(Protocol):
    """Removes a book's KB/GraphRAG data (backed by the MCP tool tier)."""

    def delete_book(self, *, user_id: str, book_id: str) -> int: ...


class BookDeletionProtocol(Protocol):
    """The deletion surface the API depends on (real + local-mock)."""

    def delete_book(
        self, *, user_id: str, book_id: str
    ) -> dict[str, int | bool]: ...


class BookDeletionService:
    def __init__(
        self,
        *,
        s3_client: Any,
        uploads_bucket: str,
        reading_results_bucket: str,
        conversations_table: Any,
        progress_table: Any,
        kb_deleter: KnowledgeBaseDeleter,
    ) -> None:
        self._s3 = s3_client
        self._uploads_bucket = uploads_bucket
        self._readings_bucket = reading_results_bucket
        self._conversations = conversations_table
        self._progress = progress_table
        self._kb = kb_deleter

    def delete_book(self, *, user_id: str, book_id: str) -> dict[str, int | bool]:
        """Delete every piece of the user's content for ``book_id``.

        Returns a summary of what was removed (for the audit log + response).
        Best-effort per store: a failure in one store is logged and does not
        abort the others, so a partially-ingested book can still be cleaned up.
        """
        summary: dict[str, int | bool] = {
            "deleted_pdf": self._delete_pdf(user_id, book_id),
            "deleted_chunks": self._delete_kb(user_id, book_id),
            "deleted_readings": self._delete_readings(user_id, book_id),
            "deleted_conversations": self._delete_conversations(user_id, book_id),
            "deleted_progress": self._delete_progress(user_id, book_id),
        }
        # Audit: the deletion is itself traceable (jobs + logs are preserved).
        logger.info("book_deleted", extra={"book_id": book_id, **summary})
        return summary

    def _delete_pdf(self, user_id: str, book_id: str) -> bool:
        key = build_upload_key(user_id, book_id)
        try:
            self._s3.delete_object(Bucket=self._uploads_bucket, Key=key)
            return True
        except Exception as exc:
            logger.info(
                "book_delete_pdf_failed",
                extra={"book_id": book_id, "error_type": type(exc).__name__},
            )
            return False

    def _delete_kb(self, user_id: str, book_id: str) -> int:
        try:
            return self._kb.delete_book(user_id=user_id, book_id=book_id)
        except Exception as exc:
            logger.info(
                "book_delete_kb_failed",
                extra={"book_id": book_id, "error_type": type(exc).__name__},
            )
            return 0

    def _delete_readings(self, user_id: str, book_id: str) -> int:
        # Readings are keyed by reading_id (== job_id), with book_id inside the
        # payload, so list the user's readings and delete those for this book.
        prefix = f"readings/{user_id}/"
        deleted = 0
        try:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self._readings_bucket, Prefix=prefix
            ):
                for obj in page.get("Contents", []) or []:
                    if self._reading_is_for_book(obj["Key"], book_id):
                        self._s3.delete_object(
                            Bucket=self._readings_bucket, Key=obj["Key"]
                        )
                        deleted += 1
        except Exception as exc:
            logger.info(
                "book_delete_readings_failed",
                extra={"book_id": book_id, "error_type": type(exc).__name__},
            )
        return deleted

    def _reading_is_for_book(self, key: str, book_id: str) -> bool:
        try:
            body = self._s3.get_object(Bucket=self._readings_bucket, Key=key)
            payload = json.loads(body["Body"].read())
            return bool(payload.get("book_id") == book_id)
        except Exception:
            return False

    def _delete_conversations(self, user_id: str, book_id: str) -> int:
        # Conversations table has no (user_id, book_id) index; query the user's
        # partition and delete those whose book_id matches.
        deleted = 0
        try:
            response = self._conversations.query(
                KeyConditionExpression="user_id = :u",
                ExpressionAttributeValues={":u": user_id},
            )
            for item in response.get("Items", []) or []:
                if item.get("book_id") == book_id:
                    self._conversations.delete_item(
                        Key={
                            "user_id": user_id,
                            "conversation_id": item["conversation_id"],
                        }
                    )
                    deleted += 1
        except Exception as exc:
            logger.info(
                "book_delete_conversations_failed",
                extra={"book_id": book_id, "error_type": type(exc).__name__},
            )
        return deleted

    def _delete_progress(self, user_id: str, book_id: str) -> bool:
        try:
            self._progress.delete_item(
                Key={"user_id": user_id, "book_id": book_id}
            )
            return True
        except Exception as exc:
            logger.info(
                "book_delete_progress_failed",
                extra={"book_id": book_id, "error_type": type(exc).__name__},
            )
            return False
