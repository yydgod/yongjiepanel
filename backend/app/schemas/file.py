"""File manager request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

MAX_PATH_LENGTH = 4096


class FileWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=MAX_PATH_LENGTH)
    content: str = ""


class FileMkdirRequest(BaseModel):
    path: str = Field(min_length=1, max_length=MAX_PATH_LENGTH)


class FileRenameRequest(BaseModel):
    path: str = Field(min_length=1, max_length=MAX_PATH_LENGTH)
    target: str = Field(min_length=1, max_length=MAX_PATH_LENGTH)
