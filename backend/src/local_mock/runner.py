"""Inline job runner for local mock mode.

Stands in for SQS + AgentCore: when a job is enqueued, the matching agent runs
synchronously in-process against the local fakes. This lets the async flows
(ingestion, adaptive reading) complete locally so the frontend's job polling
sees COMPLETED without any AWS.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.agents.adaptive_reading.agent import AdaptiveReadingAgent
from src.agents.ingestion.agent import IngestionAgent
from src.local_mock.integrations import (
    LocalContentStore,
    LocalKnowledgeBase,
    LocalReadingStore,
    MockTextGeneration,
)
from src.repositories.jobs import JobRepository


class InlineJobQueue:
    """QueuePort that runs the matching agent synchronously on enqueue."""

    def __init__(
        self,
        *,
        jobs: JobRepository,
        content: LocalContentStore,
        knowledge_base: LocalKnowledgeBase,
        reading_store: LocalReadingStore,
    ) -> None:
        self._ingestion = IngestionAgent(
            content=content, knowledge_base=knowledge_base, jobs=jobs
        )
        self._reading = AdaptiveReadingAgent(
            content=knowledge_base,
            generator=MockTextGeneration(),
            store=reading_store,
            jobs=jobs,
        )

    def send_job(
        self, message: dict[str, Any], *, dedup_id: str | None = None
    ) -> None:
        job_type = message.get("job_type")
        if job_type == "BOOK_INGESTION":
            _run(self._ingestion.handle_message(message))
        elif job_type == "ADAPTIVE_READING":
            _run(self._reading.handle_message(message))


def _run(coro: Any) -> None:
    """Run a coroutine to completion, whether or not a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    # Inside a running loop (FastAPI request): run on a fresh loop in a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, coro).result()
