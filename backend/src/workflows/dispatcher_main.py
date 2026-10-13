"""Dispatcher service entrypoint.

Assembles the SQS consumer + AgentCore invoker from settings and runs the
poll→invoke→delete loop forever. This is the container entrypoint for the
dispatcher ECS service (`Dockerfile.dispatcher`).

    python -m src.workflows.dispatcher_main
"""

from __future__ import annotations

from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.integrations.agentcore import AgentCoreInvoker
from src.integrations.sqs import SqsConsumer
from src.workflows.dispatcher import JobDispatcher

logger = get_logger(__name__)


def build_dispatcher() -> JobDispatcher:
    settings = get_settings()
    if not settings.jobs_queue_url:
        raise RuntimeError("JOBS_QUEUE_URL is required for the dispatcher")

    consumer = SqsConsumer.from_settings(settings, settings.jobs_queue_url)
    invoker = AgentCoreInvoker.from_settings(settings)
    runtime_arns = {
        "ingestion": settings.agent_runtime_arn_ingestion or "",
        "adaptive": settings.agent_runtime_arn_adaptive or "",
    }
    return JobDispatcher(
        consumer=consumer, invoker=invoker, runtime_arns=runtime_arns
    )


def main() -> None:  # pragma: no cover - process entrypoint
    settings = get_settings()
    configure_logging(settings.log_level)
    build_dispatcher().run_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
