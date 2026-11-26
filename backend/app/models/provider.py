"""LLM providers (DeepSeek / Hunyuan / Qwen / custom OpenAI-compatible)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdPk, TimestampMixin


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[IdPk]
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(24), index=True)  # deepseek | hunyuan | qwen | custom
    base_url: Mapped[str] = mapped_column(String(200))
    default_model: Mapped[str] = mapped_column(String(80))
    models: Mapped[list[str]] = mapped_column(JSON, default=list)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    timeout: Mapped[float] = mapped_column(Float, default=60.0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
