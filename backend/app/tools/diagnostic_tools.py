"""Read-only diagnostic tools (auto-execute, no confirmation)."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from app.core.errors import UNAVAILABLE, AppError
from app.core.logging import get_logger
from app.services.status_service import store
from app.tools.registry import ToolContext, ToolSpec, registry

log = get_logger("tools.diagnostic")


async def get_status(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    snapshot = store.snapshot(ctx.card_id)
    if snapshot is None:
        return {
            "ok": False,
            "summary": "尚未采集到该卡片的状态，请等待下一轮采集",
            "data": None,
        }
    return {
        "ok": True,
        "summary": f"{ctx.title} 当前状态 {snapshot.get('status')}",
        "data": snapshot,
    }


async def get_metrics(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    points = store.history(ctx.card_id)[-int(args.get("points", 30)) :]
    cpus = [p["cpu"] for p in points if p.get("cpu") is not None]
    return {
        "ok": True,
        "summary": f"最近 {len(points)} 个采样点，CPU 峰值 {max(cpus) if cpus else 0}%",
        "data": {"points": points},
    }


def _docker_logs(target: str, lines: int) -> str:
    import docker

    client = docker.from_env(timeout=5)
    container = client.containers.get(target)
    return container.logs(tail=lines, timestamps=True).decode("utf-8", "ignore")


def _journal_logs(unit: str, lines: int) -> str:
    proc = subprocess.run(
        ["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "--output=short-iso"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return proc.stdout or proc.stderr or "(无日志输出)"


async def tail_logs(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    lines = max(10, min(int(args.get("lines", 100)), 500))
    target = str(args.get("target") or ctx.target_ref)
    try:
        if ctx.card_type == "container":
            text = await asyncio.to_thread(_docker_logs, target, lines)
        elif ctx.card_type == "systemd":
            text = await asyncio.to_thread(_journal_logs, target, lines)
        else:
            raise AppError(UNAVAILABLE, f"{ctx.card_type} 类型卡片不支持日志读取", 400)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("tail_logs failed: %s", exc, extra={"tool": "tail_logs", "card_id": ctx.card_id})
        raise AppError(UNAVAILABLE, f"读取日志失败：{type(exc).__name__}", 502) from exc
    return {"ok": True, "summary": f"已读取 {lines} 行日志", "data": {"logs": text[-8000:]}}


async def list_ports(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    snapshot = store.snapshot(ctx.card_id) or {}
    ports = snapshot.get("ports") or []
    return {
        "ok": True,
        "summary": f"监听端口：{', '.join(str(p) for p in ports) or '未发现'}",
        "data": {"ports": ports},
    }


def register() -> None:
    specs = [
        ToolSpec(
            name="get_status",
            label="查询状态",
            description="读取该卡片最近一次采集到的运行状态、CPU、内存、端口。",
            risk="read",
            kinds=["container", "systemd", "port", "custom"],
            handler=get_status,
        ),
        ToolSpec(
            name="get_metrics",
            label="查询指标",
            description="读取该卡片最近若干采样点的 CPU/内存时间序列。",
            risk="read",
            kinds=["container", "systemd", "port", "custom"],
            params={"points": {"type": "integer", "description": "采样点数量，默认 30"}},
            handler=get_metrics,
        ),
        ToolSpec(
            name="tail_logs",
            label="读取日志",
            description="读取容器或 systemd unit 的尾部日志（最多 500 行）。",
            risk="read",
            kinds=["container", "systemd"],
            params={
                "lines": {"type": "integer", "description": "行数，默认 100"},
                "target": {"type": "string", "description": "可选，覆盖默认目标对象"},
            },
            handler=tail_logs,
        ),
        ToolSpec(
            name="list_ports",
            label="端口探测",
            description="列出该卡片关联服务当前监听的端口。",
            risk="read",
            kinds=["container", "systemd", "port"],
            handler=list_ports,
        ),
    ]
    for spec in specs:
        registry.register(spec)


register()
