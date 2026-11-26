"""Service cards (atomic board units) and their dedicated agents."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    icon: Mapped[str] = mapped_column(String(48), default="box")
    accent: Mapped[str] = mapped_column(String(16), default="teal")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    display_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    agent: Mapped[Agent | None] = relationship(
        back_populates="card", uselist=False, cascade="all, delete-orphan"
    )


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[IdPk]
    card_id: Mapped[str] = mapped_column(ForeignKey("service_cards.id"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), default="卡片助手")
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("providers.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(80), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    gateway: Mapped[str] = mapped_column(String(16), default="auto")  # auto | openclaw | direct
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    card: Mapped[ServiceCard] = relationship(back_populates="agent")
