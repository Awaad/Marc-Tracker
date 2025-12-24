import asyncio
import logging

from app.engine.bus import EventBus
from app.engine.tracking_manager import TrackingManager

log = logging.getLogger("app.engine")


class EngineRuntime:
    def __init__(self) -> None:
        self.bus: EventBus[object] = EventBus()
        self.tracking: TrackingManager = TrackingManager(self.bus)

        self._consumer_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._consumer_task and not self._consumer_task.done():
            return
        self._consumer_task = asyncio.create_task(self._consume_events())

    async def stop(self) -> None:
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def _consume_events(self) -> None:
        # Now we log events. Later we persist, broadcast, etc.
        while True:
            event = await self.bus.next()
            log.info("engine-event", extra={"event": type(event).__name__})
            self.bus.task_done()


engine_runtime = EngineRuntime()
