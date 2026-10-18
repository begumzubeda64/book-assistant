"""Adaptive-reading agent entrypoint.

Consumes an ``ADAPTIVE_READING`` job, runs the reading graph, stores the result
in S3 via the reading-store tool, and records job status transitions. The
``reading_id`` is the ``job_id`` so the result can be fetched by the API.

Idempotency/retry safety: terminal jobs are skipped on redelivery; the reading
result is stored under a deterministic per-user reading key.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from src.agents.adaptive_reading.graph import build_reading_graph
from src.agents.adaptive_reading.state import ReadingState
from src.agents.shared.ports import (
    BookContentPort,
    ReadingStorePort,
    TextGenerationPort,
)
from src.core.logging import get_logger
from src.models.job import JobStatus
from src.models.reading import ReadingFocus, ReadingMode, word_budget_for_minutes
from src.repositories.jobs import JobRepository

logger = get_logger(__name__)


class AdaptiveReadingAgent:
    def __init__(
        self,
        *,
        content: BookContentPort,
        generator: TextGenerationPort,
        store: ReadingStorePort,
        jobs: JobRepository,
    ) -> None:
        self._graph = build_reading_graph(content, generator)
        self._store = store
        self._jobs = jobs

    async def handle_message(self, message: dict[str, Any]) -> None:
        job_id = message["job_id"]
        job = await self._jobs.get(job_id)
        if job is None:
            logger.info("reading_job_missing", extra={"job_id": job_id})
            return
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            logger.info("reading_job_already_terminal", extra={"job_id": job_id})
            return

        await self._jobs.update_status(job_id, JobStatus.PROCESSING, progress=10)

        minutes = job.target_duration or 5
        state: ReadingState = {
            "job_id": job_id,
            "user_id": job.user_id,
            "book_id": job.book_id or "",
            "chapter_id": job.chapter_id,
            "duration_minutes": minutes,
            "mode": ReadingMode(job.mode) if job.mode else ReadingMode.BALANCED_READ,
            "focus": ReadingFocus(job.focus) if job.focus else ReadingFocus.KEY_IDEAS,
        }

        try:
            result = self._graph.invoke(state)
            payload = self._build_payload(job_id, job, minutes, result)
            location = self._store.store_reading(
                user_id=job.user_id, reading_id=job_id, payload=payload
            )
        except Exception as exc:
            logger.exception(
                "reading_failed: %s: %s",
                type(exc).__name__,
                exc,
                extra={"job_id": job_id, "error_type": type(exc).__name__},
            )
            await self._jobs.update_status(
                job_id, JobStatus.FAILED, error_code="READING_ERROR"
            )
            return

        await self._jobs.update_status(
            job_id, JobStatus.COMPLETED, progress=100, result_location=location
        )

    @staticmethod
    def _build_payload(
        job_id: str, job: Any, minutes: int, result: dict[str, Any]
    ) -> str:
        content = result.get("content", "")
        return json.dumps(
            {
                "reading_id": job_id,
                "book_id": job.book_id,
                "chapter_id": job.chapter_id,
                "mode": state_value(job.mode, ReadingMode.BALANCED_READ),
                "focus": state_value(job.focus, ReadingFocus.KEY_IDEAS),
                "target_minutes": minutes,
                "target_words": word_budget_for_minutes(minutes),
                "actual_words": len(content.split()),
                "content": content,
                "source_refs": result.get("source_refs", []),
                "created_at": datetime.now(UTC).isoformat(),
            }
        )


def state_value(raw: str | None, default: object) -> str:
    """Return the enum-string value or the default's value."""
    return raw if raw else str(getattr(default, "value", default))
