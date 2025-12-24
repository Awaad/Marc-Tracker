import asyncio
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class EventBus(Generic[T]):
    def __init__(self, maxsize: int = 10000) -> None:
        self._q: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, event: T) -> None:
        await self._q.put(event)

    async def next(self) -> T:
        return await self._q.get()

    def task_done(self) -> None:
        self._q.task_done()


@dataclass(frozen=True)
class EngineStarted:
    pass
