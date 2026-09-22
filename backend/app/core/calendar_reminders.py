"""The in-process reminder loop — runs
`calendar_reminder_service.process_due_reminders` every `_POLL_INTERVAL_
SECONDS` for as long as this web process is alive. This is a best-effort
latency improvement, not the sole delivery mechanism: a Render free-tier
web dyno can be idle-stopped and only wakes on the next request, so every
notification poll also opportunistically calls the same function scoped to
its own organization (app/api/v1/recruiter/notifications.py) as the
self-healing fallback. Neither path needs the other to be correct — the
underlying claim is a single atomic UPDATE, so firing the same reminder
twice is structurally impossible regardless of which path gets there first.

Spans every tenant, so it runs under `rls_bypass` — the third legitimate use
that helper's docstring (app/db/rls.py) anticipates: a genuine system-level
background job with no single caller's tenant to scope to, same rationale
as "resolving who a caller is before a tenant is known" or a SUPER_ADMIN
platform operation.
"""

import asyncio

from app.core.logging import get_logger
from app.db.rls import rls_bypass
from app.db.session import AsyncSessionLocal
from app.services.calendar_reminder_service import process_due_reminders

logger = get_logger(__name__)

_POLL_INTERVAL_SECONDS = 60

_task: asyncio.Task[None] | None = None


async def _poll_forever() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with rls_bypass(db):
                    fired = await process_due_reminders(db)
                await db.commit()
                if fired:
                    logger.info(
                        "Reminder loop tick", extra={"extra_fields": {"fired": fired}}
                    )
        except Exception:  # the loop must survive a transient DB hiccup, never crash
            logger.exception("Reminder loop tick failed")
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def start_reminder_loop() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(_poll_forever())


async def stop_reminder_loop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
