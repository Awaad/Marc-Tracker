from __future__ import annotations

from app.adapters.hub import AdapterEntry, adapter_hub
from app.adapters.mock import MockAdapter
from app.adapters.signal.adapter import SignalAdapter
from app.adapters.signal.service import signal_service

from app.adapters.whatsapp.adapter import WhatsAppAdapter
from app.adapters.whatsapp.service import whatsapp_service

from app.adapters.whatsapp_web.adapter import WhatsAppWebAdapter
from app.adapters.whatsapp_web.service import whatsapp_web_service

from app.core.capabilities import Platform
from app.settings import settings


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


    adapter_hub.register(
        AdapterEntry(
            platform=Platform.signal,
            factory=lambda user_id, contact_id: SignalAdapter(user_id=user_id, contact_id=contact_id),
            start_all=signal_service.start_all,
            stop_all=signal_service.stop_all,
        )
    )

    if settings.whatsapp_enabled:
        adapter_hub.register(
            AdapterEntry(
                platform=Platform.whatsapp,
                factory=lambda user_id, contact_id: WhatsAppAdapter(user_id=user_id, contact_id=contact_id),
                start_all=whatsapp_service.start_all,
                stop_all=whatsapp_service.stop_all,
            )
        )

    adapter_hub.register(
        AdapterEntry(
            platform=Platform.whatsapp_web,
            factory=lambda user_id, contact_id: WhatsAppWebAdapter(user_id=user_id, contact_id=contact_id),
            start_all=whatsapp_web_service.start_all,
            stop_all=whatsapp_web_service.stop_all,
        )
    )

   