"""Job service.

Creates jobs, enqueues them for the agent tier, and reads their status. Job
creation is idempotent: a repeated request with the same idempotency key returns
the existing job rather than creating duplicate expensive work.
"""

from __future__ import annotations

import uuid

from src.core.security.authorization import assert_owner
from src.core.security.cognito import AuthenticatedUser
from src.integrations.sqs import QueuePort
from src.models.job import Job, JobStatus, JobType
from src.repositories.jobs import JobRepository


class JobService:
    def __init__(self, *, repository: JobRepository, queue: QueuePort) -> None:
        self._repo = repository
        self._queue = queue

    async def create_and_enqueue(
        self,
        *,
        user_id: str,
        job_type: JobType,
        book_id: str | None = None,
        idempotency_key: str | None = None,
        **params: str | int | None,
    ) -> Job:
        """Create a QUEUED job and enqueue it. Idempotent on idempotency_key."""
        if idempotency_key:
            existing = await self._repo.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        job = Job(
            job_id=str(uuid.uuid4()),
            user_id=user_id,
            job_type=job_type,
            book_id=book_id,
            status=JobStatus.QUEUED,
            idempotency_key=idempotency_key,
            chapter_id=params.get("chapter_id"),  # type: ignore[arg-type]
            target_duration=params.get("target_duration"),  # type: ignore[arg-type]
            mode=params.get("mode"),  # type: ignore[arg-type]
            focus=params.get("focus"),  # type: ignore[arg-type]
        )
        created = await self._repo.create(job)

        # Only enqueue if this call created the job (create returns existing on
        # idempotency hit, which would already be enqueued).
        if created.job_id == job.job_id:
            self._queue.send_job(
                {
                    "job_id": created.job_id,
                    "job_type": created.job_type.value,
                    "user_id": created.user_id,
                    "book_id": created.book_id,
                },
                dedup_id=idempotency_key or created.job_id,
            )
        return created

    async def get_for_user(self, job_id: str, user: AuthenticatedUser) -> Job:
        """Fetch a job, enforcing ownership."""
        job = await self._repo.get(job_id)
        assert_owner(
            user, job.user_id if job else None, resource="job"
        )
        assert job is not None  # assert_owner raised if None
        return job
