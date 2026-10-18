"""Warm-up endpoint.

Called once by the frontend right after login to wake the scale-to-zero agent
runtimes, so the user's first real action (upload / read / discuss) lands on a
warm runtime instead of paying a cold start. The endpoint returns immediately
(202) and fires the pings in the background: each runtime gets a quick
``{"warmup": true}`` invoke that the agent answers instantly (no job, no model
call). Best-effort — warm-up is an optimization, never a hard dependency, so
failures are logged and ignored.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from src.api.dependencies import CurrentUser, SettingsDep
from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/warmup", tags=["warmup"])


def _warm(settings: Settings) -> None:
    from src.integrations.agentcore import AgentCoreInvoker

    invoker = AgentCoreInvoker.from_settings(settings)
    for arn in settings.warmup_runtime_arns:
        try:
            invoker.invoke(arn, {"warmup": True})
        except Exception as exc:
            logger.info(
                "warmup_ping_failed", extra={"error_type": type(exc).__name__}
            )


@router.post("", status_code=202)
async def warmup(
    _user: CurrentUser, settings: SettingsDep, background: BackgroundTasks
) -> dict[str, int]:
    """Kick off a best-effort pre-warm of the agent runtimes (returns at once)."""
    count = len(settings.warmup_runtime_arns)
    if count:
        background.add_task(_warm, settings)
    return {"scheduled": count}
