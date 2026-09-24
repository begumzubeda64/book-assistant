"""Text-generation tool (MCP).

Wraps Bedrock foundation-model inference for the adaptive-reading and discussion
agents. This is the single model-calling capability; agents never invoke Bedrock
directly. The client is injected for testability.
"""

from __future__ import annotations

import json
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class TextGenerationTool:
    def __init__(self, bedrock_runtime_client: Any, model_id: str) -> None:
        self._client = bedrock_runtime_client
        self._model_id = model_id

    def generate(self, *, prompt: str, max_words: int) -> str:
        # Approximate max tokens from a word budget (~1.4 tokens/word) with head-room.
        max_tokens = int(max_words * 1.6) + 64
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response = self._client.invoke_model(modelId=self._model_id, body=body)
        payload = json.loads(response["body"].read())
        parts = payload.get("content", [])
        text = "".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        )
        logger.info("text_generated", extra={"chars": len(text)})
        return text
