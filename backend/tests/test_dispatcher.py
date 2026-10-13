"""Tests for the SQS -> AgentCore dispatcher (routing, ack, redelivery)."""

from __future__ import annotations

import json
from typing import Any

from src.workflows.dispatcher import JobDispatcher

RUNTIMES = {
    "ingestion": "arn:aws:bedrock-agentcore:eu-central-1:1:runtime/ingestion",
    "adaptive": "arn:aws:bedrock-agentcore:eu-central-1:1:runtime/adaptive",
}


class FakeConsumer:
    def __init__(self, bodies: list[str]) -> None:
        self._messages = [
            {"body": b, "receipt_handle": f"rh-{i}"}
            for i, b in enumerate(bodies)
        ]
        self.deleted: list[str] = []

    def receive(self, *, max_messages: int, wait_seconds: int) -> list[dict[str, Any]]:
        msgs, self._messages = self._messages, []
        return msgs

    def delete(self, receipt_handle: str) -> None:
        self.deleted.append(receipt_handle)


class FakeInvoker:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def invoke(self, runtime_arn: str, payload: dict[str, Any]) -> None:
        self.calls.append((runtime_arn, payload))
        if self.fail:
            raise RuntimeError("invoke failed")


def _dispatcher(consumer: FakeConsumer, invoker: FakeInvoker) -> JobDispatcher:
    return JobDispatcher(consumer=consumer, invoker=invoker, runtime_arns=RUNTIMES)


def test_routes_ingestion_to_ingestion_runtime() -> None:
    consumer = FakeConsumer(
        [json.dumps({"job_id": "j1", "job_type": "BOOK_INGESTION"})]
    )
    invoker = FakeInvoker()
    n = _dispatcher(consumer, invoker).process_once()
    assert n == 1
    assert invoker.calls[0][0] == RUNTIMES["ingestion"]
    assert consumer.deleted == ["rh-0"]  # acked on success


def test_routes_reading_to_adaptive_runtime() -> None:
    consumer = FakeConsumer(
        [json.dumps({"job_id": "r1", "job_type": "ADAPTIVE_READING"})]
    )
    invoker = FakeInvoker()
    _dispatcher(consumer, invoker).process_once()
    assert invoker.calls[0][0] == RUNTIMES["adaptive"]


def test_failed_invoke_leaves_message_for_redelivery() -> None:
    consumer = FakeConsumer(
        [json.dumps({"job_id": "j1", "job_type": "BOOK_INGESTION"})]
    )
    invoker = FakeInvoker(fail=True)
    n = _dispatcher(consumer, invoker).process_once()
    assert n == 0
    assert consumer.deleted == []  # NOT acked -> SQS will redeliver -> DLQ


def test_unknown_job_type_is_dropped() -> None:
    consumer = FakeConsumer([json.dumps({"job_id": "x", "job_type": "DISCUSSION"})])
    invoker = FakeInvoker()
    _dispatcher(consumer, invoker).process_once()
    assert invoker.calls == []
    assert consumer.deleted == ["rh-0"]  # poison message removed


def test_malformed_message_is_dropped() -> None:
    consumer = FakeConsumer(["not-json"])
    invoker = FakeInvoker()
    _dispatcher(consumer, invoker).process_once()
    assert invoker.calls == []
    assert consumer.deleted == ["rh-0"]


def test_batch_dispatches_each_message() -> None:
    consumer = FakeConsumer([
        json.dumps({"job_id": "a", "job_type": "BOOK_INGESTION"}),
        json.dumps({"job_id": "b", "job_type": "ADAPTIVE_READING"}),
    ])
    invoker = FakeInvoker()
    n = _dispatcher(consumer, invoker).process_once()
    assert n == 2
    assert len(consumer.deleted) == 2
