from __future__ import annotations

import asyncio
import functools
import smtplib
import logging
from email.message import EmailMessage
from typing import Iterable
from functools import partial

from app.settings import settings

log = logging.getLogger("app.mailer")


def _send_email_sync(*, to: str, subject: str, text: str) -> None:
    host = getattr(settings, "smtp_host", None)
    port = int(getattr(settings, "smtp_port", 587) or 587)
    user = getattr(settings, "smtp_user", None)
    password = getattr(settings, "smtp_pass", None)
    use_tls = bool(getattr(settings, "smtp_tls", True))
    mail_from = getattr(settings, "smtp_from", None)

    if not host or not mail_from or not to:
        log.warning(
            "email skipped (missing smtp_host/smtp_from/to)",
            extra={"to": to, "smtp_host": host, "smtp_from": mail_from},
        )
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
    async def _runner():
        try:
            await asyncio.to_thread(_send_email_sync, to=to, subject=subject, text=text)
        except Exception:
            log.exception("email send failed", extra={"to": to, "subject": subject})

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        # no running loop
        try:
            _send_email_sync(to=to, subject=subject, text=text)
        except Exception:
            log.exception("email send failed (no loop)", extra={"to": to, "subject": subject})


def send_email_background_many(*, to_list: Iterable[str], subject: str, text: str) -> None:
    for to in to_list:
        send_email_background(to=to, subject=subject, text=text)