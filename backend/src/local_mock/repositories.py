"""In-memory repositories for local mock mode.

Implement the same protocols as the DynamoDB repositories but keep state in
process memory. Suitable only for a single local backend process.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.models.conversation import Conversation, Message
from src.models.job import Job, JobStatus
from src.models.progress import Progress


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._by_key: dict[str, str] = {}

    async def create(self, job: Job) -> Job:
        if job.idempotency_key and job.idempotency_key in self._by_key:
            return self._jobs[self._by_key[job.idempotency_key]]
        self._jobs[job.job_id] = job
        if job.idempotency_key:
            self._by_key[job.idempotency_key] = job.job_id
        return job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def find_by_idempotency_key(self, key: str) -> Job | None:
        job_id = self._by_key.get(key)
        return self._jobs.get(job_id) if job_id else None

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: int | None = None,
        result_location: str | None = None,
        error_code: str | None = None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = status
        job.updated_at = datetime.now(UTC)
        if progress is not None:
            job.progress = progress
        if result_location is not None:
            job.result_location = result_location
        if error_code is not None:
            job.error_code = error_code
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.now(UTC)


class InMemoryProgressRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Progress] = {}

    async def get(self, user_id: str, book_id: str) -> Progress | None:
        return self._items.get((user_id, book_id))

    async def save(self, progress: Progress) -> Progress:
        self._items[(progress.user_id, progress.book_id)] = progress
        return progress


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Conversation] = {}

    async def create(self, conversation: Conversation) -> Conversation:
        self._items[(conversation.user_id, conversation.conversation_id)] = (
            conversation
        )
        return conversation

    async def get(
        self, user_id: str, conversation_id: str
    ) -> Conversation | None:
        return self._items.get((user_id, conversation_id))

    async def list_for_book(
        self, user_id: str, book_id: str
    ) -> list[Conversation]:
        convos = [
            c
            for (uid, _cid), c in self._items.items()
            if uid == user_id and c.book_id == book_id
        ]
        convos.sort(key=lambda c: c.updated_at, reverse=True)
        return convos

    async def append_messages(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[Message],
        *,
        summary: str | None = None,
    ) -> Conversation:
        conversation = self._items[(user_id, conversation_id)]
        conversation.messages.extend(messages)
        if summary is not None:
            conversation.summary = summary
        conversation.updated_at = datetime.now(UTC)
        return conversation
