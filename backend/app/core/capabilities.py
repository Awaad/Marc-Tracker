from enum import Enum


class Platform(str, Enum):
    signal = "signal"
    sms = "sms"
    telegram = "telegram"
    whatsapp = "whatsapp"
    mock = "mock"


class Capabilities(dict):
    """
    Simple dict-like capabilities to keep JSON easy.
    Later we can make it a Pydantic model if you prefer.
    """

    @staticmethod
    def for_platform(platform: Platform) -> "Capabilities":
        # Conservative defaults (truthful).
        if platform == Platform.sms:
            # SMS can often report "delivered" via provider callbacks.
            return Capabilities(delivery_receipts=True, read_receipts=False, presence=False)
        if platform == Platform.whatsapp:
            # WhatsApp Cloud API can report delivered/read via webhooks (business).
            return Capabilities(delivery_receipts=True, read_receipts=True, presence=False)
        if platform == Platform.signal:
            # Signal can report delivery receipts in some setups (e.g., signal-cli rest).
            return Capabilities(delivery_receipts=True, read_receipts=False, presence=False)
        if platform == Platform.telegram:
            # Telegram Bot API has no delivered/read receipts; MTProto can provide some read signals
            # depending on chat type. We'll start conservative and upgrade if MTProto adapter is used.
            return Capabilities(delivery_receipts=False, read_receipts=False, presence=False)
        return Capabilities(delivery_receipts=False, read_receipts=False, presence=False)
