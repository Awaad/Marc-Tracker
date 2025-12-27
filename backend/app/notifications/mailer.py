from __future__ import annotations
import asyncio
import os
import smtplib
from email.message import EmailMessage

from app.settings import settings

def _send_email_sync(*, to: str, subject: str, text: str) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        return  # silently no-op if not configured

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        if settings.smtp_tls:
            s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_pass)
        s.send_message(msg)

def send_email_background(*, to: str, subject: str, text: str) -> None:
    # fire-and-forget; keeps endpoints fast
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _send_email_sync, to=to, subject=subject, text=text)
