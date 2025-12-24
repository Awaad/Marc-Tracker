import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.engine.bus import EventBus

log = logging.getLogger("app.engine")


@dataclass(frozen=True)
class TrackingStarted:
    user_id: int
    contact_id: int


@dataclass(frozen=True)
class TrackingStopped:
    user_id: int
    contact_id: int


class TrackingManager:
    """
    Owns per-contact background tasks (probe loops / adapter listeners).
    Later, per-contact tasks will use an Adapter to send probes and receive receipts.
    """

    def __init__(self, bus: EventBus[object]) -> None:
        self._bus = bus
        self._tasks: dict[tuple[int, int], asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def start(self, user_id: int, contact_id: int, runner: Callable[[], Awaitable[None]]) -> None:
        key = (user_id, contact_id)
        async with self._lock:
            if key in self._tasks and not self._tasks[key].done():
                log.info("tracking already running", extra={"user_id": user_id, "contact_id": contact_id})
                return

            task = asyncio.create_task(self._wrap_runner(user_id, contact_id, runner))
            self._tasks[key] = task

        await self._bus.publish(TrackingStarted(user_id=user_id, contact_id=contact_id))

    async def stop(self, user_id: int, contact_id: int) -> None:
        key = (user_id, contact_id)
        async with self._lock:
            task = self._tasks.get(key)

        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("tracker task failed on stop", extra={"user_id": user_id, "contact_id": contact_id})

        async with self._lock:
            self._tasks.pop(key, None)

        await self._bus.publish(TrackingStopped(user_id=user_id, contact_id=contact_id))

    async def _wrap_runner(self, user_id: int, contact_id: int, runner: Callable[[], Awaitable[None]]) -> None:
        log.info("tracking loop starting", extra={"user_id": user_id, "contact_id": contact_id})
        try:
            await runner()
        except asyncio.CancelledError:
            log.info("tracking loop cancelled", extra={"user_id": user_id, "contact_id": contact_id})
            raise
        except Exception:
            log.exception("tracking loop crashed", extra={"user_id": user_id, "contact_id": contact_id})
        finally:
            log.info("tracking loop ended", extra={"user_id": user_id, "contact_id": contact_id})
