"""Ingestion agent entrypoint.

Consumes a ``BOOK_INGESTION`` job message, runs the ingestion graph, and records
status transitions on the job record (PROCESSING -> COMPLETED / FAILED). The
graph calls the content and knowledge-base tools (via the MCP tool tier in
production); here they are injected as ports so the orchestration is testable.

Idempotency/retry safety: the job carries a deterministic idempotency key from
creation, and Knowledge Base ingestion is keyed by (user, book) prefix, so a
redelivered SQS message re-runs safely without duplicate expensive results.
"""

from __future__ import annotations

from typing import Any

from src.agents.ingestion.graph import build_ingestion_graph
from src.agents.ingestion.state import IngestionState
from src.agents.shared.ports import ContentStorePort, KnowledgeBasePort
from src.core.logging import get_logger
from src.models.job import JobStatus
from src.repositories.jobs import JobRepository

logger = get_logger(__name__)


class IngestionAgent:
    def __init__(
        self,
        *,
        content: ContentStorePort,
        knowledge_base: KnowledgeBasePort,
        jobs: JobRepository,
    ) -> None:
        self._graph = build_ingestion_graph(content, knowledge_base)
        self._jobs = jobs

    async def handle_message(self, message: dict[str, Any]) -> None:
        """Process one BOOK_INGESTION job message."""
        job_id = message["job_id"]
        job = await self._jobs.get(job_id)
        if job is None:
            logger.info("ingestion_job_missing", extra={"job_id": job_id})
            return
        # Idempotent: skip already-terminal jobs on redelivery.
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            logger.info(
                "ingestion_job_already_terminal",
                extra={"job_id": job_id, "status": job.status.value},
            )
            return

        await self._jobs.update_status(job_id, JobStatus.PROCESSING, progress=10)

        state: IngestionState = {
            "job_id": job_id,
            "user_id": job.user_id,
            "book_id": job.book_id or "",
            "object_key": message.get("object_key")
            or _object_key(job.user_id, job.book_id or ""),
        }

        try:
            result = self._graph.invoke(state)
        except Exception as exc:
            logger.info(
                "ingestion_failed",
                extra={"job_id": job_id, "error_type": type(exc).__name__},
            )
            await self._jobs.update_status(
                job_id, JobStatus.FAILED, error_code="INGESTION_ERROR"
            )
            return

        await self._jobs.update_status(
            job_id,
            JobStatus.COMPLETED,
            progress=100,
            result_location=result.get("ingestion_ref"),
        )


def _object_key(user_id: str, book_id: str) -> str:
    return f"uploads/{user_id}/{book_id}.pdf"
