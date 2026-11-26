"""Declarative base and shared column helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


#: reusable annotated column type (must be used inside Mapped[...] per class)
IdPk = Annotated[str, mapped_column(String(32), primary_key=True, default=new_id)]
