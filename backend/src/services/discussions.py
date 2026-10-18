"""Discussion service.

Orchestrates conversations: create a thread, post a question (load prior
context, invoke the discussion agent, persist both the question and the grounded
answer), and read a thread back. Everything is scoped to the authenticated
user_id, so a user can only access their own conversations (requirement 1.3).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from src.agents.discussion.agent import DiscussionAgentProtocol
from src.core.errors import NotFoundError
from src.core.logging import get_logger
from src.core.security.cognito import AuthenticatedUser
from src.models.conversation import (
    Conversation,
    Message,
    MessageRole,
    SourceCitation,
)
from src.repositories.conversations import ConversationRepository

logger = get_logger(__name__)


class DiscussionService:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        agent: DiscussionAgentProtocol,
    ) -> None:
        self._repo = repository
        self._agent = agent
        # Strong references to detached streaming tasks so they aren't GC'd
        # before completing (generation + persistence survive client disconnect).
        self._pending: set[Any] = set()

    async def create_conversation(
        self,
        user: AuthenticatedUser,
        book_id: str,
        title: str | None,
        persona: str | None = None,
    ) -> Conversation:
        from src.agents.discussion.personas import profile_for

        conversation = Conversation(
            user_id=user.user_id,
            conversation_id=str(uuid.uuid4()),
            book_id=book_id,
            title=title,
            # Normalize to a known persona id (defaults safely if unknown).
            persona=profile_for(persona).persona.value,
        )
        return await self._repo.create(conversation)

    async def get_conversation(
        self, user: AuthenticatedUser, conversation_id: str
    ) -> Conversation:
        conversation = await self._repo.get(user.user_id, conversation_id)
        if conversation is None:
            raise NotFoundError(
                "Conversation not found", code="CONVERSATION_NOT_FOUND"
            )
        return conversation

    async def list_for_book(
        self, user: AuthenticatedUser, book_id: str
    ) -> list[Conversation]:
        """List the user's conversations for a book (newest first)."""
        return await self._repo.list_for_book(user.user_id, book_id)

    async def post_message(
        self, user: AuthenticatedUser, conversation_id: str, question: str
    ) -> Message:
        conversation = await self.get_conversation(user, conversation_id)

        history = [(m.role.value, m.content) for m in conversation.messages]
        # Pass both the running summary of older turns and the recent turns, so
        # the model has the full conversation context (memory management).
        result = self._agent.answer(
            user_id=user.user_id,
            book_id=conversation.book_id,
            question=question,
            history=history,
            summary=conversation.summary,
            # Pass the current title so the agent can keep refreshing it while
            # it's still a placeholder (replace it once a real topic appears).
            current_title=conversation.title,
            # Persona sets the answer's voice/style (default handled downstream).
            persona=conversation.persona,
        )

        user_msg = Message(
            message_id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=question,
        )
        assistant_msg = Message(
            message_id=str(uuid.uuid4()),
            role=MessageRole.ASSISTANT,
            content=result.answer,
            citations=[
                SourceCitation.model_validate(c) for c in result.citations
            ],
        )
        await self._repo.append_messages(
            user.user_id,
            conversation_id,
            [user_msg, assistant_msg],
            summary=result.updated_summary,
            # Intent-based title from the agent (2-3 words), refreshed over the
            # opening turns; None after it stabilizes so it isn't overwritten.
            title=result.title,
        )
        return assistant_msg

    async def post_message_stream(
        self, user: AuthenticatedUser, conversation_id: str, question: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a grounded answer, persisting the full turn when it completes.

        Yields event dicts: ``{"type":"delta","text":...}`` as tokens arrive,
        then ``{"type":"final", message_id, title, citations}`` once the answer
        is complete and both messages have been persisted.

        Disconnect-safe: generation + persistence run in a DETACHED asyncio task
        that is NOT cancelled if the client goes away (the response generator
        may be cancelled on disconnect). So navigating away mid-stream still
        completes the answer server-side and saves it — it appears on return
        from the stored thread. The consumer here just relays events to the
        client while it's listening.
        """
        import asyncio

        conversation = await self.get_conversation(user, conversation_id)
        # History for the agent is the thread BEFORE this question (captured now,
        # before we persist the question, so it isn't duplicated in context).
        history = [(m.role.value, m.content) for m in conversation.messages]

        # Persist the user's question IMMEDIATELY, so if they navigate away and
        # come back mid-generation the thread still shows their message (and the
        # UI can render a "generating…" state for the pending answer).
        user_msg = Message(
            message_id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=question,
        )
        await self._repo.append_messages(
            user.user_id, conversation_id, [user_msg]
        )

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def _persist_and_final(final: dict[str, Any]) -> dict[str, Any]:
            answer_text = str(final.get("answer") or "")
            citations: list[Any] = list(final.get("citations") or [])
            # Append ONLY the assistant answer — the user message is already
            # persisted above.
            assistant_msg = Message(
                message_id=str(uuid.uuid4()),
                role=MessageRole.ASSISTANT,
                content=answer_text,
                citations=[SourceCitation.model_validate(c) for c in citations],
            )
            await self._repo.append_messages(
                user.user_id,
                conversation_id,
                [assistant_msg],
                summary=final.get("updated_summary"),  # type: ignore[arg-type]
                title=final.get("title"),  # type: ignore[arg-type]
            )
            return {
                "type": "final",
                "message_id": assistant_msg.message_id,
                "title": final.get("title"),
                "citations": [c.model_dump() for c in assistant_msg.citations],
            }

        def _emit(event: dict[str, Any]) -> None:
            # Thread-safe hand-off of a stream event to the consumer's queue.
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def _run_blocking_stream() -> dict[str, Any]:
            parts: list[str] = []
            final: dict[str, Any] = {"answer": "", "citations": []}
            for ev in self._agent.answer_stream(
                user_id=user.user_id,
                book_id=conversation.book_id,
                question=question,
                history=history,
                summary=conversation.summary,
                current_title=conversation.title,
                persona=conversation.persona,
            ):
                if ev.type == "delta":
                    parts.append(ev.text)
                    _emit({"type": "delta", "text": ev.text})
                else:
                    final = {
                        "answer": ev.answer or "".join(parts),
                        "citations": ev.citations or [],
                        "updated_summary": ev.updated_summary,
                        "title": ev.title,
                    }
            return final

        async def _generate_and_persist() -> None:
            try:
                final = await asyncio.to_thread(_run_blocking_stream)
                # Shield persistence so a cancelled client can't lose the answer.
                final_event = await asyncio.shield(_persist_and_final(final))
                _emit(final_event)
            except Exception:
                logger.exception("discussion_stream_failed")
                _emit({"type": "error"})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        # Detached: survives client disconnect so generation completes + saves.
        task = asyncio.ensure_future(_generate_and_persist())
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
