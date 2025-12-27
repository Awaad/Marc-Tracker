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

    extensions:
    - get_profile(): return display/avatar/status when supported
    - get_presence(): return presence string when supported
    """

    @abstractmethod
    async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        raise NotImplementedError

    @abstractmethod
    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        raise NotImplementedError

    async def get_profile(self, *, user_id: int, contact_id: int) -> Optional[dict]:
        """
         returns dict with any of:
          - display_name: str
          - avatar_url: str
          - status_text: str
        Return None if unsupported.
        """
        return None

    async def get_presence(self, *, user_id: int, contact_id: int) -> Optional[str]:
        """
        returns a presence string like:
          'online' | 'offline' | 'unknown' | ...
        Return None if unsupported.
        """
        return None

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
