from sqlalchemy import String, Integer, Float, ForeignKey, Text, Index, BigInteger, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship



class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    user_name: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    platform: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(256), default="")
    display_number: Mapped[str] = mapped_column(String(64), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    platform_meta_json: Mapped[str] = mapped_column(Text, default="{}")
    notify_online: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_last_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    notify_last_sent_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    user: Mapped["User"] = relationship()


class TrackerPoint(Base):
    __tablename__ = "tracker_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)

    device_id: Mapped[str] = mapped_column(String(256))
    state: Mapped[str] = mapped_column(String(32))
    timestamp_ms: Mapped[int] = mapped_column(Integer, index=True)

    rtt_ms: Mapped[float] = mapped_column(Float)
    avg_ms: Mapped[float] = mapped_column(Float)
    median_ms: Mapped[float] = mapped_column(Float)
    threshold_ms: Mapped[float] = mapped_column(Float)

    probe_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class PlatformProbe(Base):
    __tablename__ = "platform_probes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)

    platform: Mapped[str] = mapped_column(String(32), index=True)
    probe_id: Mapped[str] = mapped_column(String(64), index=True)

    # For Signal, receipts include timestamps of the original sent message.
    platform_message_ts: Mapped[int | None] = mapped_column(BigInteger, index=True)

    sent_at_ms: Mapped[int] = mapped_column(BigInteger)
    delivered_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    read_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    send_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    platform_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


    __table_args__ = (
        Index("ix_platform_probe_unique", "platform", "probe_id", unique=True),
    )