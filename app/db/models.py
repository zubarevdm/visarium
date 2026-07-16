from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 384  # multilingual-e5-small; синхронизировано с миграцией 0001


class Base(DeclarativeBase):
    pass


class User(Base):
    """Псевдонимизация: telegram_id — единственная связь с внешним миром,
    ФИО/телефоны/документы не хранятся нигде (152-ФЗ, минимизация)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    language: Mapped[str] = mapped_column(String(8), default="ru")
    subscription_status: Mapped[str] = mapped_column(String(16), default="free")  # free | active
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    teaser_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    citizenship: Mapped[str | None] = mapped_column(String(8))
    entry_date: Mapped[date | None] = mapped_column(Date)
    migration_registered: Mapped[bool | None] = mapped_column(Boolean)
    has_patent: Mapped[bool | None] = mapped_column(Boolean)
    patent_date: Mapped[date | None] = mapped_column(Date)
    has_rvp: Mapped[bool | None] = mapped_column(Boolean)
    has_vnj: Mapped[bool | None] = mapped_column(Boolean)
    goal: Mapped[str | None] = mapped_column(String(16))
    current_stage: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DialogState(Base):
    __tablename__ = "dialog_state"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    collected_facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    due_date: Mapped[date] = mapped_column(Date)
    notified_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_3d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | done | expired

    __table_args__ = (Index("ix_deadlines_due_status", "due_date", "status"),)


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    applies_to: Mapped[list[str]] = mapped_column(ARRAY(Text))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    source_file: Mapped[str] = mapped_column(String(255))
    kb_version: Mapped[str] = mapped_column(String(64))


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    telegram_payment_charge_id: Mapped[str] = mapped_column(String(255), unique=True)
    stars_amount: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(16), default="1m")
    status: Mapped[str] = mapped_column(String(16), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
