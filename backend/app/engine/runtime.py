import asyncio
import logging

from app.engine.bus import EventBus
from app.engine.tracking_manager import TrackingManager
from app.engine.classifier import ClassifierV1
from app.engine.correlator import Correlator
from app.engine.insights import InsightsManager
from app.storage.points_repo import TrackerPointsRepo
from app.notifications.notify_manager import NotifyManager


log = logging.getLogger("app.engine")


class EngineRuntime:
    def __init__(self) -> None:
        self.bus: EventBus[object] = EventBus()
        self.tracking: TrackingManager = TrackingManager(self.bus)

        self.classifier = ClassifierV1()
        self.correlator = Correlator(self.classifier)
        self.points_repo = TrackerPointsRepo()

       
        self.insights = InsightsManager(window_size=600, broadcast_interval_ms=2000)
        self.notifier = NotifyManager()
        log.info("notifier enabled=%s", bool(self.notifier))

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
        while True:
            event = await self.bus.next()
            log.info("engine-event", extra={"event": type(event).__name__})
            self.bus.task_done()


engine_runtime = EngineRuntime()
