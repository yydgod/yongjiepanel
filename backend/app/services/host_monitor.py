"""Host-level metrics monitor: CPU / memory / disk / network / processes.

设计与卡片采集完全隔离：只用 psutil 读取本机指标，不依赖 Docker 或 systemd，
因此即使容器运行时不可用，主页看板仍然有数据。速率类指标（网络、磁盘 IO）
通过相邻两次采样的计数差计算，首次采样记为 0。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import platform
import socket
import threading
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

import psutil

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("host.monitor")

MB = 1024 * 1024
GB = 1024 * MB
SKIP_FSTYPES = {"squashfs", "devtmpfs", "tmpfs", "ramfs", "overlay", "nsfs", "proc", "sysfs"}


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _delta_rate(current: float | None, previous: float | None, elapsed: float) -> float:
    """Bytes/s between two counter readings."""
    if current is None or previous is None or elapsed <= 0:
        return 0.0
    return max(0.0, (current - previous) / elapsed)


def _kbps(rate: float) -> float:
    return round(rate / 1024, 1)


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


class HostMonitor:
    def __init__(self, history: int = 120, interval: float = 3.0) -> None:
        self.interval = interval
        self._history: deque[dict[str, Any]] = deque(maxlen=history)
        self._snapshot: dict[str, Any] = self._unavailable("尚未完成首次采样")
        self._previous: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="host-monitor")
        log.info("主机监控已启动 interval=%ss history=%s", self.interval, self._history.maxlen)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            await asyncio.to_thread(self.sample)
            await asyncio.sleep(self.interval)

    async def force_sample(self) -> dict[str, Any]:
        return await asyncio.to_thread(self.sample)

    # ------------------------------------------------------------------ sampling
    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "available": False,
            "error": {"code": "unavailable", "message": reason},
            "collected_at": None,
            "system": {},
            "cpu": {},
            "memory": {},
            "disk": {},
            "network": {},
            "processes": [],
            "health": {"status": "unknown", "reasons": [reason]},
            "history": [],
        }

    def sample(self) -> dict[str, Any]:
        started = time.time()
        try:
            payload = self._collect(started)
        except Exception as exc:  # noqa: BLE001 - 采集失败不能影响 API
            log.warning("主机指标采集失败: %s", exc)
            with self._lock:
                self._snapshot = self._unavailable(str(exc))
            return self._snapshot

        with self._lock:
            self._snapshot = payload
            self._history.append(payload.pop("history_point"))
            payload["history"] = list(self._history)
        return payload

    def _collect(self, started: float) -> dict[str, Any]:
        previous = self._previous
        elapsed = started - float(previous.get("ts", started))

        per_core = [round(value, 1) for value in psutil.cpu_percent(interval=None, percpu=True)]
        cpu_percent = round(sum(per_core) / len(per_core), 1) if per_core else psutil.cpu_percent(interval=None)
        frequency = psutil.cpu_freq()

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        disk_io = psutil.disk_io_counters()
        disk_read_rate = _delta_rate(
            disk_io.read_bytes if disk_io else None, previous.get("disk_read"), elapsed
        )
        disk_write_rate = _delta_rate(
            disk_io.write_bytes if disk_io else None, previous.get("disk_write"), elapsed
        )
        partitions = self._partitions()

        network_io = psutil.net_io_counters(pernic=True)
        addresses = psutil.net_if_addrs()
        interfaces: list[dict[str, Any]] = []
        up_rate = down_rate = 0.0
        for name, counters in network_io.items():
            if name == "lo":
                continue
            last = previous.get("net", {}).get(name, {})
            sent = _delta_rate(counters.bytes_sent, last.get("sent"), elapsed)
            recv = _delta_rate(counters.bytes_recv, last.get("recv"), elapsed)
            up_rate += sent
            down_rate += recv
            ip = next(
                (addr.address for addr in addresses.get(name, []) if addr.family == socket.AF_INET),
                "—",
            )
            interfaces.append(
                {
                    "name": name,
                    "ip": ip,
                    "up_kbps": _kbps(sent),
                    "down_kbps": _kbps(recv),
                    "sent_gb": round(counters.bytes_sent / GB, 2),
                    "recv_gb": round(counters.bytes_recv / GB, 2),
                }
            )
        interfaces.sort(key=lambda item: item["down_kbps"] + item["up_kbps"], reverse=True)

        total_disk_gb = round(sum(item["total_gb"] for item in partitions), 1)
        used_disk_gb = round(sum(item["used_gb"] for item in partitions), 1)
        disk_percent = round(used_disk_gb / total_disk_gb * 100, 1) if total_disk_gb else 0.0

        boot = psutil.boot_time()
        load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        cores = psutil.cpu_count() or 1
        reasons = self._health_reasons(cpu_percent, memory.percent, disk_percent)

        payload: dict[str, Any] = {
            "available": True,
            "error": None,
            "collected_at": _iso(started),
            "interval": self.interval,
            "system": {
                "hostname": socket.gethostname(),
                "os": f"{platform.system()} {platform.release()}",
                "kernel": platform.release(),
                "arch": platform.machine(),
                "cpu_model": _cpu_model(),
                "cores": cores,
                "physical_cores": psutil.cpu_count(logical=False) or cores,
                "python": platform.python_version(),
                "boot_time": _iso(boot),
                "uptime_seconds": int(max(0, started - boot)),
                "process_count": len(psutil.pids()),
                "user_count": len(psutil.users()),
                "load": [round(value, 2) for value in load],
            },
            "cpu": {
                "percent": cpu_percent,
                "per_core": per_core,
                "freq_mhz": round(frequency.current, 0) if frequency else None,
            },
            "memory": {
                "total_mb": round(memory.total / MB),
                "used_mb": round(memory.used / MB),
                "available_mb": round(memory.available / MB),
                "percent": round(memory.percent, 1),
                "swap_total_mb": round(swap.total / MB),
                "swap_used_mb": round(swap.used / MB),
                "swap_percent": round(swap.percent, 1),
            },
            "disk": {
                "total_gb": total_disk_gb,
                "used_gb": used_disk_gb,
                "percent": disk_percent,
                "read_kbps": _kbps(disk_read_rate),
                "write_kbps": _kbps(disk_write_rate),
                "partitions": partitions,
            },
            "network": {
                "up_kbps": _kbps(up_rate),
                "down_kbps": _kbps(down_rate),
                "total_sent_gb": round(sum(item["sent_gb"] for item in interfaces), 2),
                "total_recv_gb": round(sum(item["recv_gb"] for item in interfaces), 2),
                "interfaces": interfaces[:6],
            },
            "processes": self._top_processes(),
            "health": {
                "status": "critical" if len(reasons) >= 2 else "warning" if reasons else "ok",
                "reasons": reasons,
            },
            "history_point": {
                "ts": _iso(started),
                "cpu": cpu_percent,
                "mem": round(memory.percent, 1),
                "net_up": _kbps(up_rate),
                "net_down": _kbps(down_rate),
                "disk_read": _kbps(disk_read_rate),
                "disk_write": _kbps(disk_write_rate),
            },
        }

        self._previous = {
            "ts": started,
            "disk_read": disk_io.read_bytes if disk_io else None,
            "disk_write": disk_io.write_bytes if disk_io else None,
            "net": {
                name: {"sent": counters.bytes_sent, "recv": counters.bytes_recv}
                for name, counters in network_io.items()
            },
        }
        return payload

    @staticmethod
    def _partitions() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for part in psutil.disk_partitions(all=False):
            if part.fstype in SKIP_FSTYPES:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            items.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / GB, 1),
                    "used_gb": round(usage.used / GB, 1),
                    "percent": round(usage.percent, 1),
                }
            )
        items.sort(key=lambda item: item["percent"], reverse=True)
        return items

    @staticmethod
    def _top_processes(limit: int = 6) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                memory_info = info.get("memory_info")
                rss = memory_info.rss if memory_info else 0
                items.append(
                    {
                        "pid": info["pid"],
                        "name": (info.get("name") or "?")[:28],
                        "memory_mb": round(rss / MB, 1),
                        "cpu_percent": round(proc.cpu_percent(interval=None), 1),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        items.sort(key=lambda item: item["memory_mb"], reverse=True)
        return items[:limit]

    @staticmethod
    def _health_reasons(cpu: float, memory: float, disk: float) -> list[str]:
        reasons: list[str] = []
        if cpu >= 90:
            reasons.append(f"CPU 使用率 {cpu:.0f}% 偏高")
        if memory >= 90:
            reasons.append(f"内存使用率 {memory:.0f}% 偏高")
        if disk >= 90:
            reasons.append(f"磁盘使用率 {disk:.0f}% 偏高")
        return reasons

    # ------------------------------------------------------------------ read
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = dict(self._snapshot)
            payload["history"] = list(self._history)
            payload["interval"] = self.interval
            return payload


host_monitor = HostMonitor(
    history=settings.host_history_points,
    interval=settings.host_interval,
)
