from __future__ import annotations

import logging
from dataclasses import dataclass
from sys import platform
from typing import Awaitable, Callable

from app.adapters.base import BaseAdapter
from app.core.capabilities import Platform

log = logging.getLogger("app.adapters")


# Factory returns a *per-contact* adapter instance (or a wrapper around shared resources)
AdapterFactory = Callable[[int, int], BaseAdapter]  # (user_id, contact_id) -> adapter


@dataclass
class AdapterEntry:
    platform: Platform
    factory: AdapterFactory
    start_all: Callable[[], Awaitable[None]] | None = None
    stop_all: Callable[[], Awaitable[None]] | None = None


class AdapterHub:
    """
    - register(platform, factory, start_all?, stop_all?)
    - create(platform, user_id, contact_id) -> adapter
    - init_all() / shutdown_all(): allows running all adapter services together at startup
      (useful for Signal listeners, WhatsApp webhook processing queues, telemetry, etc.)
    """

    def __init__(self) -> None:
        self._entries: dict[Platform, AdapterEntry] = {}

    def register(self, entry: AdapterEntry) -> None:
        self._entries[entry.platform] = entry
        log.info("adapter registered", extra={"platform": entry.platform.value})

    def create(self, platform: Platform, user_id: int, contact_id: int) -> BaseAdapter:
        entry = self._entries.get(platform)
        if not entry:
            raise RuntimeError(f"No adapter registered for platform={platform.value}")
        return entry.factory(user_id, contact_id)
    
    
    def supports(self, platform: Platform) -> bool:
        return platform in self._entries


    async def init_all(self) -> None:
        # Start platform-wide adapter services (no-op for mock; later Signal/WhatsApp will use this)
        for entry in self._entries.values():
            if entry.start_all:
                log.info("adapter start_all", extra={"platform": entry.platform.value})
                await entry.start_all()

    async def shutdown_all(self) -> None:
        for entry in self._entries.values():
            if entry.stop_all:
                log.info("adapter stop_all", extra={"platform": entry.platform.value})
                await entry.stop_all()


adapter_hub = AdapterHub()
