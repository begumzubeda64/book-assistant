"""GraphRAG retrieval tool (MCP).

Retrieves passages from the Bedrock Knowledge Base (backed by Neptune Analytics)
for the discussion agent. Retrieval is scoped to the requesting user's content
via a metadata filter on ``user_id``, so it never returns another user's book or
derived graph context (security.md). Source references come straight from the
retrieved metadata; citations are never fabricated.
"""

from __future__ import annotations

from typing import Any

from src.agents.shared.ports import RetrievedPassage
from src.core.logging import get_logger

logger = get_logger(__name__)


class GraphRAGRetrievalTool:
    def __init__(
        self, bedrock_agent_runtime_client: Any, knowledge_base_id: str
    ) -> None:
        self._client = bedrock_agent_runtime_client
        self._kb_id = knowledge_base_id

    def retrieve(
        self, *, user_id: str, book_id: str, query: str, top_k: int = 8
    ) -> list[RetrievedPassage]:
        response = self._client.retrieve(
            knowledgeBaseId=self._kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": top_k,
                    # Scope retrieval to this user's content for this book.
                    "filter": {
                        "andAll": [
                            {"equals": {"key": "user_id", "value": user_id}},
                            {"equals": {"key": "book_id", "value": book_id}},
                        ]
                    },
                }
            },
        )
        passages = [
            self._to_passage(result)
            for result in response.get("retrievalResults", [])
        ]
        logger.info(
            "graphrag_retrieved",
            extra={"book_id": book_id, "result_count": len(passages)},
        )
        return passages

    @staticmethod
    def _to_passage(result: dict[str, Any]) -> RetrievedPassage:
        content = result.get("content", {})
        metadata = result.get("metadata", {})
        return RetrievedPassage(
            text=content.get("text", ""),
            chunk_id=metadata.get("chunk_id"),
            chapter_title=metadata.get("chapter_title"),
            section=metadata.get("section"),
            page=metadata.get("page"),
            score=result.get("score"),
        )
