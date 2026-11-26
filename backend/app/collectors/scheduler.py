"""Background collection loop (asyncio + thread-offloaded blocking calls)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.collectors.base import Snapshot
from app.collectors.registry import registry
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import ServiceCard
from app.services.status_service import StatusStore, store

log = get_logger("collector.scheduler")


def _load_targets() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(ServiceCard)
            .filter(ServiceCard.enabled.is_(True))
            .order_by(ServiceCard.sort_order)
            .all()
        )
        return [
            {"card_id": row.id, "card_type": row.card_type, "target": row.target_ref}
            for row in rows
        ]
    finally:
        db.close()


class CollectScheduler:
    def __init__(self, status_store: StatusStore | None = None) -> None:
        self.store = status_store or store
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._loop(), name="collect-loop")
        log.info("采集调度器已启动 interval=%ss", settings.collect_interval)

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
            log.info("采集调度器已停止")

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.error("采集循环异常: %s", exc, exc_info=True)
            await asyncio.sleep(max(1, settings.collect_interval))

    async def run_once(self) -> dict[str, Any]:
        started = time.perf_counter()
        cards = await asyncio.to_thread(_load_targets)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for card in cards:
            grouped.setdefault(card["card_type"], []).append(card)

        diagnostics: list[dict[str, Any]] = []
        applied = 0
        for kind, items in grouped.items():
            collector = registry.get(kind)
            if collector is None:
                diagnostics.append(
                    {
                        "kind": kind,
                        "label": kind,
                        "available": False,
                        "reason": f"未注册 {kind} 类型的采集实现",
                    }
                )
                for item in items:
                    self._apply(
                        item["card_id"],
                        Snapshot.unavailable(
                            item["target"], "unavailable", f"不支持的卡片类型：{kind}", kind
                        ),
                    )
                continue

            ok, reason = await asyncio.to_thread(collector.available)
            diagnostics.append(
                {"kind": kind, "label": collector.label, "available": ok, "reason": reason}
            )
            if not ok:
                for item in items:
                    self._apply(
                        item["card_id"],
                        Snapshot.unavailable(item["target"], "unavailable", reason or "采集不可用", kind),
                    )
                continue

            targets = sorted({item["target"] for item in items})
            try:
                snapshots = await asyncio.wait_for(
                    collector.collect(targets), timeout=settings.collect_timeout
                )
            except TimeoutError:
                diagnostics[-1]["reason"] = "采集超时"
                snapshots = {
                    target: Snapshot.unavailable(target, "timeout", "采集超时", kind)
                    for target in targets
                }
            except Exception as exc:  # noqa: BLE001
                diagnostics[-1]["reason"] = f"采集失败：{type(exc).__name__}"
                snapshots = {
                    target: Snapshot.unavailable(target, "upstream_error", str(exc)[:160], kind)
                    for target in targets
                }

            for item in items:
                snap = snapshots.get(item["target"]) or Snapshot.unavailable(
                    item["target"], "not_found", "未获得采集结果", kind
                )
                self._apply(item["card_id"], self._decorate(snap))
                applied += 1

        duration_ms = int((time.perf_counter() - started) * 1000)
        self.store.set_diagnostics(diagnostics, duration_ms)
        return {"cards": applied, "duration_ms": duration_ms, "diagnostics": diagnostics}

    @staticmethod
    def _decorate(snap: Snapshot) -> Snapshot:
        """Escalate to warning when a running target looks saturated."""
        if snap.status == "running":
            cpu = snap.cpu_percent or 0
            mem_ratio = 0.0
            if snap.memory_mb and snap.memory_limit_mb:
                mem_ratio = snap.memory_mb / snap.memory_limit_mb * 100
            if cpu >= 85 or mem_ratio >= 90:
                snap.status = "warning"
                snap.detail = f"{snap.detail} · 资源占用偏高"
        return snap

    def _apply(self, card_id: str, snap: Snapshot) -> None:
        self.store.put(card_id, snap.to_dict())


scheduler = CollectScheduler()
