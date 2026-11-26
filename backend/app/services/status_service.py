"""In-memory runtime state: latest snapshot + rolling metric history.

Config lives in the database; volatile state lives here so a 5s collect loop
never causes write amplification.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings


class StatusStore:
    def __init__(self, history_points: int | None = None) -> None:
        self._history_points = history_points or settings.metric_history_points
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self._history_points)
        )
        self._diagnostics: list[dict[str, Any]] = []
        self._last_run: datetime | None = None
        self._last_duration_ms: int | None = None
        self._lock = threading.Lock()

    # ---- writers -------------------------------------------------------
    def put(self, card_id: str, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self._snapshots[card_id] = snapshot
            point = {
                "ts": snapshot.get("collected_at"),
                "cpu": snapshot.get("cpu_percent"),
                "mem": snapshot.get("memory_mb"),
            }
            if point["cpu"] is not None or point["mem"] is not None:
                self._history[card_id].append(point)

    def set_diagnostics(self, items: list[dict[str, Any]], duration_ms: int) -> None:
        with self._lock:
            self._diagnostics = items
            self._last_run = datetime.now(UTC)
            self._last_duration_ms = duration_ms

    # ---- readers -------------------------------------------------------
    def snapshot(self, card_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._snapshots.get(card_id)

    def history(self, card_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history.get(card_id, ()))

    def diagnostics(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._diagnostics)

    def health(self) -> dict[str, Any]:
        with self._lock:
            snapshots = list(self._snapshots.values())
            return {
                "last_run": self._last_run.isoformat(timespec="seconds") if self._last_run else None,
                "duration_ms": self._last_duration_ms,
                "tracked_cards": len(snapshots),
                "collectors": list(self._diagnostics),
            }

    def overview(self) -> dict[str, Any]:
        with self._lock:
            snapshots = list(self._snapshots.values())
        counts = {"running": 0, "stopped": 0, "warning": 0, "unavailable": 0, "unknown": 0}
        cpu_values, mem_ratios = [], []
        for snap in snapshots:
            status = snap.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
            if snap.get("cpu_percent") is not None:
                cpu_values.append(float(snap["cpu_percent"]))
            if snap.get("memory_mb") is not None and snap.get("memory_limit_mb"):
                mem_ratios.append(float(snap["memory_mb"]) / float(snap["memory_limit_mb"]) * 100)
        return {
            "counts": counts,
            "total": len(snapshots),
            "avg_cpu": round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else None,
            "avg_mem_ratio": round(sum(mem_ratios) / len(mem_ratios), 1) if mem_ratios else None,
        }

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()
            self._history.clear()


store = StatusStore()
