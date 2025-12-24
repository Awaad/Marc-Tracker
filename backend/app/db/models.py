from sqlalchemy import String, Integer, Float, ForeignKey, Text, Index, BigInteger, JSON
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

    __table_args__ = (
        Index("ix_platform_probe_unique", "platform", "probe_id", unique=True),
    )