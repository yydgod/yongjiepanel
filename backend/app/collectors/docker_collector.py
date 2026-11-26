"""Docker container collector (read-only, docker SDK)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.collectors.base import BaseCollector, Snapshot, uptime_from
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("collector.docker")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class DockerCollector(BaseCollector):
    kind = "container"
    label = "Docker 容器"

    def __init__(self) -> None:
        self._client: Any = None
        self._reason: str | None = "尚未初始化"

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        import docker  # imported lazily so a broken SDK never breaks startup

        client = docker.from_env(timeout=settings.collect_timeout)
        client.ping()
        self._client = client
        self._reason = None
        return client

    def available(self) -> tuple[bool, str | None]:
        if not settings.docker_enabled:
            return False, "已通过 DOCKER_ENABLED=false 关闭 Docker 采集"
        try:
            self._connect()
            return True, None
        except Exception as exc:  # noqa: BLE001 - degrade, never raise
            self._client = None
            self._reason = (
                f"无法连接 Docker：{type(exc).__name__}。"
                "请确认 /var/run/docker.sock 已挂载且当前用户有访问权限。"
            )
            return False, self._reason

    def _collect_one(self, target: str) -> Snapshot:
        try:
            client = self._connect()
            container = client.containers.get(target)
            attrs = container.attrs or {}
            state = attrs.get("State", {})
            raw_status = state.get("Status", "unknown")
            cpu_percent, mem_mb = None, None
            try:
                stats = container.stats(stream=False)
                cpu_percent = self._cpu_percent(stats)
                mem_mb = self._memory_mb(stats)
            except Exception as exc:  # noqa: BLE001
                log.warning("docker stats 失败: %s", exc, extra={"target": target})

            status_map = {
                "running": "running",
                "restarting": "warning",
                "paused": "warning",
                "created": "stopped",
                "exited": "stopped",
                "dead": "unavailable",
                "removing": "stopped",
            }
            network = attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
            ports = sorted(
                {
                    int(binding["HostPort"])
                    for bindings in network.values()
                    if bindings
                    for binding in bindings
                    if binding.get("HostPort")
                }
            )
            return Snapshot(
                target=target,
                status=status_map.get(raw_status, "unknown"),
                cpu_percent=cpu_percent,
                memory_mb=mem_mb,
                uptime_seconds=uptime_from(_parse_ts(state.get("StartedAt"))),
                ports=ports,
                detail=f"{attrs.get('Config', {}).get('Image', '')} · {raw_status}",
                collector=self.kind,
                extra={
                    "container_id": (attrs.get("Id") or "")[:12],
                    "image": attrs.get("Config", {}).get("Image", ""),
                    "restart_count": attrs.get("RestartCount", 0),
                },
            )
        except Exception as exc:  # noqa: BLE001
            message = f"容器不存在或不可访问：{type(exc).__name__}"
            log.warning("docker collect failed: %s", exc, extra={"target": target})
            return Snapshot.unavailable(target, "not_found", message, self.kind)

    @staticmethod
    def _cpu_percent(stats: dict[str, Any]) -> float | None:
        cpu = stats.get("cpu_stats", {})
        pre = stats.get("precpu_stats", {})
        cpu_total = cpu.get("cpu_usage", {}).get("total_usage")
        pre_total = pre.get("cpu_usage", {}).get("total_usage")
        system_total = cpu.get("system_cpu_usage")
        pre_system = pre.get("system_cpu_usage")
        if None in (cpu_total, pre_total, system_total, pre_system):
            return None
        cpu_delta = cpu_total - pre_total
        system_delta = system_total - pre_system
        if cpu_delta <= 0 or system_delta <= 0:
            return 0.0
        online = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage", [])) or 1
        return (cpu_delta / system_delta) * online * 100.0

    @staticmethod
    def _memory_mb(stats: dict[str, Any]) -> float | None:
        mem = stats.get("memory_stats", {})
        usage = mem.get("usage")
        if usage is None:
            return None
        cache = (mem.get("stats") or {}).get("inactive_file", 0)
        return max(0.0, (usage - cache) / (1024 * 1024))

    async def collect(self, targets: list[str]) -> dict[str, Snapshot]:
        if not targets:
            return {}
        results = await asyncio.gather(
            *(asyncio.to_thread(self._collect_one, target) for target in targets)
        )
        return {snap.target: snap for snap in results}
