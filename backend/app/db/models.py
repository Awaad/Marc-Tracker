from sqlalchemy import String, Integer, Float, ForeignKey
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
