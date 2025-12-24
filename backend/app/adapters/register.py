from __future__ import annotations

from app.adapters.hub import AdapterEntry, adapter_hub
from app.adapters.mock import MockAdapter
from app.core.capabilities import Platform


def register_adapters() -> None:
    # Mock adapter: per-contact instance, no global services needed
    adapter_hub.register(
        AdapterEntry(
            platform=Platform.mock,
            factory=lambda user_id, contact_id: MockAdapter(),
            start_all=None,
            stop_all=None,
        )
    )

    # Placeholders 
    # adapter_hub.register(AdapterEntry(platform=Platform.signal, factory=..., start_all=..., stop_all=...))
    # adapter_hub.register(AdapterEntry(platform=Platform.whatsapp, factory=..., start_all=..., stop_all=...))
