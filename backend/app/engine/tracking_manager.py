from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Any

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
    reason: str  # "stopped" | "crashed" | "finished"


async def _maybe_bus_emit(bus: Any, event: object) -> None:
   
    if bus is None:
        return

    fn = None
    for name in ("emit", "publish", "send", "put_nowait", "put"):
        cand = getattr(bus, name, None)
        if cand:
            fn = cand
            break

    if not fn:
        return

    try:
        res = fn(event)
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        # Never let event publishing crash tracking
        log.debug("bus emit failed (ignored)", exc_info=True)


class TrackingManager:
    """
    Owns per-(user,contact,platform) background tasks.

    Key behavior:
    - start_platform replaces any existing task for the same key
    - tasks are auto-removed on finish/crash/cancel
    - list_running filters out done tasks
    """

    def __init__(self, bus: Any = None) -> None:
        self.bus = bus
        self._tasks: dict[tuple[int, int, str], asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def start_platform(
        self,
        user_id: int,
        contact_id: int,
        platform: str,
        runner: Callable[[], Awaitable[None]],
    ) -> None:
        key = (user_id, contact_id, platform)

        # serialize start/stop to avoid races
        async with self._lock:
            # stop existing
            t = self._tasks.pop(key, None)
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            async def _wrapped() -> None:
                reason = "finished"
                await _maybe_bus_emit(self.bus, TrackingStarted(user_id, contact_id, platform))
                try:
                    await runner()
                except asyncio.CancelledError:
                    reason = "stopped"
                    raise
                except Exception:
                    reason = "crashed"
                    log.exception(
                        "tracking task crashed",
                        extra={"user_id": user_id, "contact_id": contact_id, "platform": platform},
                    )
                finally:
                    # CRITICAL cleanup so /running doesn't lie
                    async with self._lock:
                        self._tasks.pop(key, None)
                    await _maybe_bus_emit(self.bus, TrackingStopped(user_id, contact_id, platform, reason=reason))

            task = asyncio.create_task(_wrapped(), name=f"track:{user_id}:{contact_id}:{platform}")
            self._tasks[key] = task

    async def stop_platform(self, user_id: int, contact_id: int, platform: str) -> None:
        key = (user_id, contact_id, platform)
        async with self._lock:
            t = self._tasks.pop(key, None)
        if not t:
            return
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def stop_all_for_contact(self, user_id: int, contact_id: int) -> None:
        async with self._lock:
            keys = [k for k in self._tasks.keys() if k[0] == user_id and k[1] == contact_id]
        for (_, _, plat) in keys:
            await self.stop_platform(user_id, contact_id, plat)

    async def is_running_platform(self, user_id: int, contact_id: int, platform: str) -> bool:
        key = (user_id, contact_id, platform)
        async with self._lock:
            t = self._tasks.get(key)
            if not t:
                return False
            if t.done():
                # cleanup if somehow left behind
                self._tasks.pop(key, None)
                return False
            return True

    async def list_running(self, user_id: int) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        async with self._lock:
            # opportunistic cleanup of done tasks
            for key, t in list(self._tasks.items()):
                uid, cid, plat = key
                if t.done():
                    self._tasks.pop(key, None)
                    continue
                if uid != user_id:
                    continue
                out.setdefault(cid, []).append(plat)
        return out
