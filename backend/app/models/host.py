"""Host model — single local row today, ready for multi-host aggregation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdPk, TimestampMixin


class Host(Base, TimestampMixin):
    __tablename__ = "hosts"

    id: Mapped[IdPk]
    name: Mapped[str] = mapped_column(String(64), default="local")
    kind: Mapped[str] = mapped_column(String(16), default="local")  # local | agent
    address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="online")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
