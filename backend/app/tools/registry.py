"""Tool registry — card quick-action capabilities.

Risk levels drive the confirmation flow: `read` tools execute immediately,
`destructive` tools require a one-shot confirm token + audit record.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.core.errors import DENIED, AppError

Risk = Literal["read", "destructive"]


class ToolContext(Protocol):
    card_id: str
    card_type: str
    target_ref: str
    title: str


@dataclass(slots=True)
class ToolSpec:
    name: str
    label: str
    description: str
    risk: Risk
    kinds: list[str]
    params: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    handler: Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.params or {},
                    "required": self.required,
                    "additionalProperties": False,
                },
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise RuntimeError(f"tool 重复注册: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        spec = self._tools.get(name)
        if spec is None:
            raise AppError(DENIED, f"未知工具: {name}", 400)
        return spec

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def for_card_type(self, kind: str) -> list[ToolSpec]:
        return [spec for spec in self._tools.values() if kind in spec.kinds]

    def openai_schemas(self, allowed: list[str] | None, kind: str) -> list[dict[str, Any]]:
        available = {spec.name for spec in self.for_card_type(kind)}
        names = [name for name in (allowed or []) if name in available]
        if not names:
            names = ["get_status", "get_metrics"]
        return [self._tools[name].schema() for name in names if name in self._tools]


registry = ToolRegistry()
