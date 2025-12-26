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
    platform: str


@dataclass(frozen=True)
class TrackingStopped:
    user_id: int
    contact_id: int
    platform: str


class TrackingManager:
    """
    Owns per-contact background tasks (probe loops / adapter listeners).
    Later, per-contact tasks will use an Adapter to send probes and receive receipts.
    """

    def __init__(self, bus: EventBus[object]) -> None:
        self._bus = bus
        # key = (user_id, contact_id, platform)
        self._tasks: dict[tuple[int, int, str], asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def start_platform(
        self,
        user_id: int,
        contact_id: int,
        platform: str,
        runner: Callable[[], Awaitable[None]],
    ) -> None:
        key = (user_id, contact_id, platform)
        async with self._lock:
            if key in self._tasks and not self._tasks[key].done():
                log.info("tracking already running", extra={"user_id": user_id, "contact_id": contact_id, "platform": platform})
                return

            task = asyncio.create_task(self._wrap_runner(user_id, contact_id, platform, runner))
            self._tasks[key] = task

        await self._bus.publish(TrackingStarted(user_id=user_id, contact_id=contact_id, platform=platform))

    async def stop(self, user_id: int, contact_id: int, platform: str) -> None:
        key = (user_id, contact_id, platform)
        async with self._lock:
            task = self._tasks.get(key)

        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("tracker task failed on stop", extra={"user_id": user_id, "contact_id": contact_id, "platform": platform})

        async with self._lock:
            self._tasks.pop(key, None)

        await self._bus.publish(TrackingStopped(user_id=user_id, contact_id=contact_id, platform=platform))

    async def stop_all_for_contact(self, user_id: int, contact_id: int) -> None:
        async with self._lock:
            keys = [k for k in self._tasks.keys() if k[0] == user_id and k[1] == contact_id]
        # stop outside lock
        for (_, _, platform) in keys:
            await self.stop_platform(user_id, contact_id, platform)

    async def _wrap_runner(self, user_id: int, contact_id: int, platform: str, runner: Callable[[], Awaitable[None]]) -> None:
        log.info("tracking loop starting", extra={"user_id": user_id, "contact_id": contact_id, "platform": platform})
        try:
            await runner()
        except asyncio.CancelledError:
            log.info("tracking loop cancelled", extra={"user_id": user_id, "contact_id": contact_id, "platform": platform})
            raise
        except Exception:
            log.exception("tracking loop crashed", extra={"user_id": user_id, "contact_id": contact_id, "platform": platform})
        finally:
            log.info("tracking loop ended", extra={"user_id": user_id, "contact_id": contact_id, "platform": platform})

        
    async def is_running(self, user_id: int, contact_id: int, platform: str) -> bool:
        key = (user_id, contact_id, platform)
        async with self._lock:
            task = self._tasks.get(key)
            return bool(task and not task.done())


    async def list_running(self, user_id: int) -> list[int]:
        async with self._lock:
            running: dict[int, set[str]] = {}
            for (uid, cid, platform), task in self._tasks.items():
                 if uid != user_id:
                    continue
                 if task.done():
                    continue
                 running.setdefault(cid, set()).add(platform)
            return {cid: sorted(list(platforms)) for cid, platforms in running.items()}


     # Back-compat helpers (optional): keep old names if you want existing call-sites to compile.
    async def start(self, user_id: int, contact_id: int, runner: Callable[[], Awaitable[None]]) -> None:
        # default to contact's platform at call-site going forward
        await self.start_platform(user_id, contact_id, "default", runner)

    async def stop(self, user_id: int, contact_id: int) -> None:
        await self.stop_all_for_contact(user_id, contact_id)

    async def is_running(self, user_id: int, contact_id: int) -> bool:
        # if any platform is running for this contact
        running = await self.list_running(user_id)
        return bool(running.get(contact_id))