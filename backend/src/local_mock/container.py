"""Process-singleton container for local mock mode.

All local fakes share one set of in-memory stores for the lifetime of the
backend process, so data written by one request (e.g. an uploaded book or a
completed job) is visible to the next.
"""

from __future__ import annotations

from functools import lru_cache

from src.local_mock.integrations import (
    LocalBlobStore,
    LocalBookDeletion,
    LocalContentStore,
    LocalKnowledgeBase,
    LocalReadingStore,
    LocalStorage,
    MockTextGeneration,
)
from src.local_mock.repositories import (
    InMemoryConversationRepository,
    InMemoryJobRepository,
    InMemoryProgressRepository,
)
from src.local_mock.runner import InlineJobQueue


class LocalMockContainer:
    def __init__(self) -> None:
        # Stores
        self.blobs = LocalBlobStore()
        self.jobs = InMemoryJobRepository()
        self.progress = InMemoryProgressRepository()
        self.conversations = InMemoryConversationRepository()
        self.knowledge_base = LocalKnowledgeBase()
        self.reading_store = LocalReadingStore()

        # Integrations
        self.storage = LocalStorage(self.blobs)
        self.content = LocalContentStore(self.blobs)
        self.generator = MockTextGeneration()

        # Inline runner (SQS + AgentCore stand-in) shares the same stores.
        self.queue = InlineJobQueue(
            jobs=self.jobs,
            content=self.content,
            knowledge_base=self.knowledge_base,
            reading_store=self.reading_store,
        )

        # Book deletion over the same in-memory stores.
        self.book_deletion = LocalBookDeletion(
            blobs=self.blobs,
            knowledge_base=self.knowledge_base,
            reading_store=self.reading_store,
            conversations=self.conversations,
            progress=self.progress,
        )


@lru_cache
def get_local_mock_container() -> LocalMockContainer:
    """Return the singleton container for this process."""
    return LocalMockContainer()
