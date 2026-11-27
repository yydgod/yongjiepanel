"""Card request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CardBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    subtitle: str | None = Field(default=None, max_length=160)
    card_type: str = Field(default="container", max_length=32)
    target_ref: str = Field(min_length=1, max_length=200)
    group_name: str = Field(default="默认分组", max_length=64)
    icon: str = Field(default="box", max_length=48)
    accent: str = Field(default="teal", max_length=16)
    display_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class CardCreate(CardBase):
    host_id: str | None = None
    sort_order: int | None = None


class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    subtitle: str | None = Field(default=None, max_length=160)
    card_type: str | None = None
    target_ref: str | None = Field(default=None, min_length=1, max_length=200)
    group_name: str | None = Field(default=None, max_length=64)
    icon: str | None = None
    accent: str | None = None
    display_config: dict[str, Any] | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class CardOut(CardBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    host_id: str
    sort_order: int
    status: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ReorderItem(BaseModel):
    id: str
    sort_order: int = Field(ge=0)


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(min_length=1)


class CardActionRequest(BaseModel):
    action: Literal["start", "stop", "restart"]


class CardTypeSpec(BaseModel):
    kind: str
    label: str
    icon: str
    accent: str
    description: str
    target_label: str
    target_placeholder: str
    target_pattern: str
    tools: list[str]
    metrics: list[str]
    display_defaults: dict[str, Any]
