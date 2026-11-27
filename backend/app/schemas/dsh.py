"""dsh workspace request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    title: str | None = Field(default=None, max_length=120)


class WorkspaceBootstrapRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    directory: str | None = Field(default=None, max_length=64)
