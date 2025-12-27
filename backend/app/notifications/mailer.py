from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.settings import settings


def _send_email_sync(*, to: str, subject: str, text: str) -> None:
    host = getattr(settings, "smtp_host", None)
    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = getattr(settings, "smtp_user", None)
    password = getattr(settings, "smtp_pass", None)
    use_tls = bool(getattr(settings, "smtp_tls", True))
    mail_from = getattr(settings, "smtp_from", None)

    if not host or not mail_from or not to:
        return

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)

    with smtplib.SMTP(host, port, timeout=20) as s:
        if use_tls:
            s.starttls()
        if user:
            s.login(user, password or "")
        s.send_message(msg)


def send_email_background(*, to: str, subject: str, text: str) -> None:
    # Fire-and-forget in a thread, do not block requests.
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _send_email_sync, to=to, subject=subject, text=text)
    except RuntimeError:
        # No running loop (rare), just send synchronously.
        _send_email_sync(to=to, subject=subject, text=text)


def send_email_background_many(*, to_list: Iterable[str], subject: str, text: str) -> None:
    for to in to_list:
        send_email_background(to=to, subject=subject, text=text)
