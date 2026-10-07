"""End-to-end local-mock flow: upload -> ingest -> reading -> discussion, in memory."""

from __future__ import annotations

import pytest
from src.agents.discussion.agent import DiscussionAgent
from src.core.security.cognito import AuthenticatedUser
from src.local_mock.container import LocalMockContainer
from src.models.job import JobType
from src.schemas.progress import ProgressUpdate
from src.schemas.uploads import PresignUploadRequest
from src.services.discussions import DiscussionService
from src.services.jobs import JobService
from src.services.progress import ProgressService
from src.services.uploads import UploadService

USER = AuthenticatedUser(user_id="local-dev-user")


def _upload_service(c: LocalMockContainer) -> UploadService:
    return UploadService(
        storage=c.storage,
        jobs=JobService(repository=c.jobs, queue=c.queue),
        verify_object_exists=False,
    )


@pytest.mark.asyncio
async def test_full_local_mock_journey() -> None:
    c = LocalMockContainer()

    # 1. Upload (presign returns a local sentinel; no real S3).
    uploads = _upload_service(c)
    presigned = uploads.presign(
        USER,
        PresignUploadRequest(
            filename="book.pdf",
            content_type="application/pdf",
            size_bytes=1000,
            authorized_confirmation=True,
        ),
    )
    assert presigned.upload_url.startswith("local-mock://")

    # 2. Complete -> ingestion job runs inline and completes.
    ingest_job = await uploads.complete_and_ingest(
        USER, presigned.book_id, presigned.object_key
    )
    done = await c.jobs.get(ingest_job.job_id)
    assert done is not None and done.status.value == "COMPLETED"
    assert c.knowledge_base.get_chunks(
        user_id=USER.user_id, book_id=presigned.book_id
    )

    # 3. Adaptive reading job runs inline and stores a result.
    jobs = JobService(repository=c.jobs, queue=c.queue)
    reading_job = await jobs.create_and_enqueue(
        user_id=USER.user_id,
        job_type=JobType.ADAPTIVE_READING,
        book_id=presigned.book_id,
        target_duration=5,
        mode="balanced_read",
        focus="key_ideas",
    )
    reading = await c.reading_store.get(USER.user_id, reading_job.job_id)
    assert reading is not None
    assert "mock" in reading["content"].lower()
    assert reading["target_words"] == 750

    # 4. Discussion runs inline with GraphRAG over the in-memory chunks.
    discussions = DiscussionService(
        repository=c.conversations,
        agent=DiscussionAgent(
            retriever=c.knowledge_base, generator=c.generator
        ),
    )
    conv = await discussions.create_conversation(USER, presigned.book_id, None)
    answer = await discussions.post_message(
        USER, conv.conversation_id, "What is this about?"
    )
    assert "mock" in answer.content.lower()

    # 5. Progress save/get roundtrip.
    progress = ProgressService(repository=c.progress)
    await progress.save_progress(
        USER.user_id, presigned.book_id, ProgressUpdate(position=10)
    )
    saved = await progress.get_progress(USER.user_id, presigned.book_id)
    assert saved is not None and saved.position == 10
