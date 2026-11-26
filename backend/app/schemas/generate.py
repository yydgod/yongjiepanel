"""AI card generation schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateCardRequest(BaseModel):
    description: str = Field(min_length=4, max_length=2000)
    provider_id: str | None = None


class CardDraft(BaseModel):
    title: str = "未命名服务"
    subtitle: str | None = None
    card_type: str = "container"
    target_ref: str = ""
    group_name: str = "AI 生成"
    icon: str = "sparkles"
    accent: str = "teal"
    display_config: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    model_hint: str | None = None
    rationale: str = ""
    channel: str = "mock"


class CustomizeCardRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=1000)


class CustomizeCardResult(BaseModel):
    title: str
    subtitle: str | None = None
    group_name: str
    icon: str
    accent: str
    display_config: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str = ""
    tools: list[str] = Field(default_factory=list)
    rationale: str = ""
    channel: str = "mock"


class GenerateCardResponse(BaseModel):
    draft: CardDraft
    channel: str
    warnings: list[str] = Field(default_factory=list)
