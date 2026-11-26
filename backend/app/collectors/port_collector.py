"""Port / process collector: maps a listening TCP port to its owning process."""

from __future__ import annotations

import asyncio
import re

from app.collectors.base import BaseCollector, Snapshot
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("collector.port")

PORT_RE = re.compile(r"^(?:(tcp|udp)/)?(\d{1,5})(?:@(tcp|udp))?$", re.IGNORECASE)


def parse_port(target: str) -> tuple[str, int]:
    match = PORT_RE.match(target.strip())
    if not match:
        raise ValueError("端口格式应为 8080 或 tcp/8080")
    proto = (match.group(1) or match.group(3) or "tcp").lower()
    port = int(match.group(2))
    if not 0 < port < 65536:
        raise ValueError("端口超出范围")
    return proto, port


class PortCollector(BaseCollector):
    kind = "port"
    label = "端口服务"

    def available(self) -> tuple[bool, str | None]:
        if not settings.port_enabled:
            return False, "已通过 PORT_ENABLED=false 关闭端口采集"
        try:
            import psutil

            psutil.net_connections(kind="inet")
            return True, None
        except Exception as exc:  # noqa: BLE001
            return False, f"psutil 无法读取网络连接（可能缺少权限）：{type(exc).__name__}"

    def _collect_one(self, target: str) -> Snapshot:
        try:
            proto, port = parse_port(target)
        except ValueError as exc:
            return Snapshot.unavailable(target, "validation", str(exc), self.kind)

        try:
            import psutil

            kind = "tcp" if proto == "tcp" else "udp"
            conns = psutil.net_connections(kind=kind)
            owners = [c for c in conns if c.laddr and c.laddr.port == port]
            if not owners:
                return Snapshot(
                    target=target,
                    status="stopped",
                    detail=f"{proto}/{port} 未在监听",
                    collector=self.kind,
                )
            listening = next((c for c in owners if c.status == psutil.CONN_LISTEN), owners[0])
            pid = listening.pid
            if not pid:
                return Snapshot(
                    target=target,
                    status="running",
                    ports=[port],
                    detail=f"{proto}/{port} 监听中（无法读取进程信息，需更高权限）",
                    collector=self.kind,
                )

            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=None)
            memory_mb = process.memory_info().rss / (1024 * 1024)
            uptime = None
            try:
                import time

                uptime = int(time.time() - process.create_time())
            except Exception:  # noqa: BLE001
                uptime = None
            return Snapshot(
                target=target,
                status="running",
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                uptime_seconds=uptime,
                ports=[port],
                detail=f"{process.name()} (pid {pid})",
                collector=self.kind,
                extra={"pid": pid, "process_name": process.name(), "proto": proto},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("port collect failed: %s", exc, extra={"target": target})
            return Snapshot.unavailable(target, "denied", type(exc).__name__, self.kind)

    async def collect(self, targets: list[str]) -> dict[str, Snapshot]:
        if not targets:
            return {}
        results = await asyncio.gather(
            *(asyncio.to_thread(self._collect_one, target) for target in targets)
        )
        return {snap.target: snap for snap in results}
