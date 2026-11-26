"""LLM provider schemas — API keys are write-only, never echoed back."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: str = Field(default="custom", max_length=24)
    base_url: str = Field(min_length=1, max_length=200)
    default_model: str = Field(default="", max_length=80)
    models: list[str] = Field(default_factory=list)
    api_key: str | None = Field(default=None, description="留空表示不修改已有 key")
    extra: dict[str, Any] = Field(default_factory=dict)
    temperature: float = Field(default=0.3, ge=0, le=2)
    timeout: float = Field(default=60.0, ge=5, le=300)
    is_default: bool = False
    enabled: bool = True


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    base_url: str
    default_model: str
    models: list[str]
    extra: dict[str, Any]
    temperature: float
    timeout: float
    is_default: bool
    enabled: bool
    has_key: bool = False
    api_key_masked: str = ""
    created_at: datetime


class ProviderTestResult(BaseModel):
    ok: bool
    latency_ms: int | None = None
    model: str | None = None
    channel: str | None = None
    message: str = ""
    sample: str | None = None


class ProviderPreset(BaseModel):
    kind: str
    label: str
    base_url: str
    models: list[str]
    docs: str
