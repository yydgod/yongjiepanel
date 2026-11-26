"""Chat / tool-call schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None


class ToolCallOut(BaseModel):
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    risk: Literal["read", "destructive"] = "read"
    status: Literal["executed", "pending_confirmation", "failed"] = "executed"
    summary: str = ""


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_name: str | None = None
    channel: str | None = None
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    card_id: str
    title: str
    channel: str
    messages: list[MessageOut] = Field(default_factory=list)


class ChatReply(BaseModel):
    session_id: str
    content: str
    channel: str
    tool_calls: list[ToolCallOut] = Field(default_factory=list)
    pending: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] | None = None


class ConfirmRequest(BaseModel):
    token: str = Field(min_length=4, max_length=48)


class ConfirmResult(BaseModel):
    ok: bool
    tool_name: str
    status: str
    result: dict[str, Any] | None = None
    message: str = ""


class PendingActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    card_id: str
    tool_name: str
    params: dict[str, Any]
    status: str
    expires_at: datetime
    created_at: datetime
