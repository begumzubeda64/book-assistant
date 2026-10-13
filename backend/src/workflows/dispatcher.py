"""Job dispatcher: SQS -> AgentCore bridge.

A long-running consumer that polls the job queue and invokes the matching
AgentCore agent runtime (AgentCore runtimes are not a native SQS event source).
Runs as its own ECS service (the dispatcher tier), keeping the FastAPI service
stateless.

Semantics:
- Routes by ``job_type`` (BOOK_INGESTION -> ingestion runtime, ADAPTIVE_READING
  -> adaptive runtime). Discussion is synchronous/direct-invoke, not queued.
- At-least-once: a message is deleted only after a successful invoke; on failure
  it stays on the queue and SQS redelivers, moving to the DLQ after
  maxReceiveCount. Agents are idempotent, so redelivery is safe.
- The SQS receive/delete surface is behind a port so the loop is unit-testable
  without AWS.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.core.logging import get_logger
from src.integrations.agentcore import AgentInvokerPort
from src.models.job import JobType

logger = get_logger(__name__)


class SqsConsumerPort(Protocol):
    def receive(self, *, max_messages: int, wait_seconds: int) -> list[dict[str, Any]]:
        """Return messages, each a dict with 'body' (str) and 'receipt_handle'."""
        ...

    def delete(self, receipt_handle: str) -> None:
        """Acknowledge a successfully processed message."""
        ...


class JobDispatcher:
    def __init__(
        self,
        *,
        consumer: SqsConsumerPort,
        invoker: AgentInvokerPort,
        runtime_arns: dict[str, str],
    ) -> None:
        self._consumer = consumer
        self._invoker = invoker
        # Map job type -> agent runtime ARN.
        self._routes = {
            JobType.BOOK_INGESTION.value: runtime_arns.get("ingestion", ""),
            JobType.ADAPTIVE_READING.value: runtime_arns.get("adaptive", ""),
        }

    def process_once(self, *, max_messages: int = 10, wait_seconds: int = 20) -> int:
        """Poll once and dispatch each message. Returns the number dispatched."""
        messages = self._consumer.receive(
            max_messages=max_messages, wait_seconds=wait_seconds
        )
        dispatched = 0
        for message in messages:
            if self._handle(message):
                dispatched += 1
        return dispatched

    def _handle(self, message: dict[str, Any]) -> bool:
        try:
            body = json.loads(message["body"])
        except (json.JSONDecodeError, KeyError):
            # Malformed message: drop it so it doesn't loop forever.
            logger.info("dispatcher_bad_message")
            self._consumer.delete(message["receipt_handle"])
            return False

        job_type = body.get("job_type")
        runtime_arn = self._routes.get(job_type, "")
        if not runtime_arn:
            logger.info("dispatcher_unknown_job_type", extra={"job_type": job_type})
            # Unknown/unroutable type: delete to avoid a poison-message loop.
            self._consumer.delete(message["receipt_handle"])
            return False

        try:
            self._invoker.invoke(runtime_arn, body)
        except Exception as exc:
            # Leave the message on the queue for redelivery (-> DLQ after N).
            logger.info(
                "dispatcher_invoke_failed",
                extra={"job_type": job_type, "error_type": type(exc).__name__},
            )
            return False

        self._consumer.delete(message["receipt_handle"])
        return True

    def run_forever(self) -> None:  # pragma: no cover - the service entrypoint
        logger.info("dispatcher_started")
        while True:
            self.process_once()
