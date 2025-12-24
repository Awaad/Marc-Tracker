from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass(frozen=True)
class AdapterProbe:
    probe_id: str
    sent_at_ms: int
    platform_message_id: Optional[str] = None


@dataclass(frozen=True)
class AdapterReceipt:
    probe_id: str
    device_id: str
    received_at_ms: int
    status: str  # "delivered", "read", "error", etc.
    platform_message_id: Optional[str] = None


class BaseAdapter(ABC):
    """
    Platform adapter contract.

    - send_probe() sends a probe and returns a probe_id (and optionally platform message id).
    - receipts() yields AdapterReceipt for receipts/status updates.
    """

    @abstractmethod
    async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        raise NotImplementedError

    @abstractmethod
    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
