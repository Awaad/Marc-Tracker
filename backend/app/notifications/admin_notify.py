from __future__ import annotations

from app.notifications.mailer import send_email_background
from app.settings import settings


def notify_admin(*, subject: str, text: str) -> None:
    to = getattr(settings, "admin_notify_email", None)
    if not to:
        return
    send_email_background(to=to, subject=subject, text=text)


def notify_admin_login(*, user_email: str, user_id: int, when_ms: int) -> None:
    notify_admin(
        subject=f"Marc-Tracker Login: user_id={user_id}",
        text=(
            f"Event: login\n"
            f"user_id: {user_id}\n"
            f"user_email: {user_email}\n"
            f"when_ms: {when_ms}\n"
        ),
    )


def notify_admin_tracking_start(
    *,
    user_email: str,
    user_id: int,
    contact_id: int,
    contact_label: str,
    platform: str,
    when_ms: int,
) -> None:
    notify_admin(
        subject=f"Tracking started: {contact_label} ({platform})",
        text=(
            f"Event: tracking_start\n"
            f"user_id: {user_id}\n"
            f"user_email: {user_email}\n"
            f"contact_id: {contact_id}\n"
            f"contact_label: {contact_label}\n"
            f"platform: {platform}\n"
            f"when_ms: {when_ms}\n"
        ),
    )
