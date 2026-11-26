"""Collector contract: the single extension point for new service kinds."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class Snapshot:
    """Normalized runtime state consumed by the API / UI."""

    target: str
    status: str = "unknown"  # running | stopped | warning | unavailable | unknown
    cpu_percent: float | None = None
    memory_mb: float | None = None
    memory_limit_mb: float | None = None
    uptime_seconds: int | None = None
    ports: list[int] = field(default_factory=list)
    detail: str = ""
    collector: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "status": self.status,
            "cpu_percent": None if self.cpu_percent is None else round(self.cpu_percent, 2),
            "memory_mb": None if self.memory_mb is None else round(self.memory_mb, 1),
            "memory_limit_mb": (
                None if self.memory_limit_mb is None else round(self.memory_limit_mb, 1)
            ),
            "uptime_seconds": self.uptime_seconds,
            "ports": self.ports,
            "detail": self.detail,
            "collector": self.collector,
            "extra": self.extra,
            "error": self.error,
            "collected_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }

    @classmethod
    def unavailable(cls, target: str, code: str, message: str, collector: str = "") -> Snapshot:
        return cls(
            target=target,
            status="unavailable",
            detail=message,
            collector=collector,
            error={"code": code, "message": message},
        )


class BaseCollector(ABC):
    kind: str = "custom"
    label: str = "自定义"

    @abstractmethod
    def available(self) -> tuple[bool, str | None]:
        """Return (usable, reason_when_unusable). Must never raise."""

    @abstractmethod
    async def collect(self, targets: list[str]) -> dict[str, Snapshot]:
        """Map target_ref -> Snapshot. Partial failures must degrade per target."""


def uptime_from(started: datetime | None) -> int | None:
    if not started:
        return None
    now = datetime.now(UTC)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return max(0, int((now - started).total_seconds()))
