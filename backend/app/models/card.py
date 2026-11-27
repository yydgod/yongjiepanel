"""Service cards (atomic board units)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdPk, TimestampMixin


class ServiceCard(Base, TimestampMixin):
    __tablename__ = "service_cards"

    id: Mapped[IdPk]
    host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    subtitle: Mapped[str | None] = mapped_column(String(160), nullable=True)
    card_type: Mapped[str] = mapped_column(String(32), index=True)
    target_ref: Mapped[str] = mapped_column(String(160))
    group_name: Mapped[str] = mapped_column(String(64), default="默认分组")
    workspace_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    icon: Mapped[str] = mapped_column(String(48), default="box")
    accent: Mapped[str] = mapped_column(String(16), default="teal")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    display_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
