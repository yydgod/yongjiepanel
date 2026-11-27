"""Terminal request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TerminalCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=64)


class TerminalExecRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=4000)
    timeout: float | None = Field(default=None, ge=1, le=120)
