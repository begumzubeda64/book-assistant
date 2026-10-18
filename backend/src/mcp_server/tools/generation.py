"""Text-generation tool (MCP).

Wraps Bedrock foundation-model inference for the adaptive-reading and discussion
agents. This is the single model-calling capability; agents never invoke Bedrock
directly. The client is injected for testability.

Supports both a buffered call (``generate``) and a token-streaming call
(``generate_stream``) built on Bedrock ``invoke_model_with_response_stream``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


def _max_tokens(max_words: int) -> int:
    # Approximate max tokens from a word budget (~1.4 tokens/word) with head-room.
    return int(max_words * 1.6) + 64


def _body(prompt: str, max_words: int) -> str:
    return json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": _max_tokens(max_words),
            "messages": [{"role": "user", "content": prompt}],
        }
    )


class TextGenerationTool:
    def __init__(self, bedrock_runtime_client: Any, model_id: str) -> None:
        self._client = bedrock_runtime_client
        self._model_id = model_id

    def generate(self, *, prompt: str, max_words: int) -> str:
        response = self._client.invoke_model(
            modelId=self._model_id, body=_body(prompt, max_words)
        )
        payload = json.loads(response["body"].read())
        parts = payload.get("content", [])
        text = "".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        )
        logger.info("text_generated", extra={"chars": len(text)})
        return text

    def generate_stream(self, *, prompt: str, max_words: int) -> Iterator[str]:
        """Yield text deltas as the model produces them (Bedrock streaming).

        Uses ``invoke_model_with_response_stream`` and emits the incremental
        ``content_block_delta`` text pieces. Callers can accumulate the full
        answer by concatenating the deltas.
        """
        response = self._client.invoke_model_with_response_stream(
            modelId=self._model_id, body=_body(prompt, max_words)
        )
        total = 0
        for event in response.get("body", []):
            chunk = event.get("chunk")
            if not chunk:
                continue
            data = json.loads(chunk["bytes"])
            if data.get("type") != "content_block_delta":
                continue
            delta = data.get("delta") or {}
            piece = delta.get("text", "")
            if piece:
                total += len(piece)
                yield piece
        logger.info("text_stream_generated", extra={"chars": total})
