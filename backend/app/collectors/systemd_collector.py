"""systemd unit collector via argv-only `systemctl show`."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from datetime import datetime

from app.collectors.base import BaseCollector, Snapshot, uptime_from
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("collector.systemd")

UNIT_RE = re.compile(r"^[A-Za-z0-9@._:\-]{1,120}$")
PROPS = "ActiveState,SubState,MainPID,MemoryCurrent,ActiveEnterTimestamp,ExecMainStartTimestamp,Description"


class SystemdCollector(BaseCollector):
    kind = "systemd"
    label = "systemd 服务"

    def available(self) -> tuple[bool, str | None]:
        if not settings.systemd_enabled:
            return False, "已通过 SYSTEMD_ENABLED=false 关闭 systemd 采集"
        if not shutil.which("systemctl"):
            return False, "未找到 systemctl 命令"
        if not os.path.isdir("/run/systemd/system"):
            return False, "当前环境未运行 systemd（常见于容器内），无法读取 unit 状态"
        try:
            proc = subprocess.run(
                ["systemctl", "is-system-running"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            state = (proc.stdout or proc.stderr or "").strip()
            if state in ("offline", "unknown", ""):
                return False, f"systemd 状态异常：{state or '无响应'}"
            return True, None
        except Exception as exc:  # noqa: BLE001
            return False, f"systemctl 调用失败：{type(exc).__name__}"

    def _collect_one(self, target: str) -> Snapshot:
        unit = target.strip()
        if not UNIT_RE.match(unit):
            return Snapshot.unavailable(target, "denied", "unit 名称包含非法字符", self.kind)
        try:
            args = ["systemctl", "show", unit]
            for prop in PROPS.split(","):
                args.extend(["-p", prop])
            args.append("--no-pager")
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode != 0:
                return Snapshot.unavailable(
                    target, "not_found", (proc.stderr or "unit 不存在").strip()[:200], self.kind
                )
            values: dict[str, str] = {}
            for line in proc.stdout.splitlines():
                if "=" in line:
                    key, _, val = line.partition("=")
                    values[key.strip()] = val.strip()
            active = values.get("ActiveState", "unknown")
            sub = values.get("SubState", "unknown")
            if active in ("", "[not set]"):
                return Snapshot.unavailable(target, "not_found", "unit 不存在或无状态", self.kind)
            pid = values.get("MainPID", "0")
            mem = values.get("MemoryCurrent", "[not set]")
            active_ts = values.get("ActiveEnterTimestamp", "")
            exec_ts = values.get("ExecMainStartTimestamp", "")
            description = values.get("Description", "")
            status_map = {
                "active": "running",
                "activating": "warning",
                "deactivating": "warning",
                "reloading": "warning",
                "failed": "unavailable",
                "inactive": "stopped",
            }
            cpu_percent = None
            if pid.isdigit() and int(pid) > 0:
                try:
                    import psutil

                    cpu_percent = psutil.Process(int(pid)).cpu_percent(interval=None)
                except Exception:  # noqa: BLE001
                    cpu_percent = None
            memory_mb = None
            if mem.lstrip("-").isdigit() and int(mem) > 0:
                memory_mb = int(mem) / (1024 * 1024)
            label = f"systemd · {active}/{sub}"
            if description:
                label = f"{label} · {description}"
            return Snapshot(
                target=unit,
                status=status_map.get(active, "unknown"),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                uptime_seconds=uptime_from(self._parse(exec_ts) or self._parse(active_ts)),
                ports=self._ports_for_pid(pid),
                detail=label,
                collector=self.kind,
                extra={"main_pid": int(pid) if pid.isdigit() else None, "sub_state": sub},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("systemd collect failed: %s", exc, extra={"target": target})
            return Snapshot.unavailable(target, "upstream_error", type(exc).__name__, self.kind)

    @staticmethod
    def _parse(value: str) -> datetime | None:
        for fmt in ("%a %Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %Z"):
            try:
                return datetime.strptime(value, fmt).astimezone()
            except ValueError:
                continue
        return None

    @staticmethod
    def _ports_for_pid(pid: str) -> list[int]:
        if not pid.isdigit():
            return []
        try:
            import psutil

            process = psutil.Process(int(pid))
            ports: set[int] = set()
            for conn in process.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr:
                    ports.add(conn.laddr.port)
            return sorted(ports)
        except Exception:  # noqa: BLE001
            return []

    async def collect(self, targets: list[str]) -> dict[str, Snapshot]:
        if not targets:
            return {}
        results = await asyncio.gather(
            *(asyncio.to_thread(self._collect_one, target) for target in targets)
        )
        return {snap.target: snap for snap in results}
