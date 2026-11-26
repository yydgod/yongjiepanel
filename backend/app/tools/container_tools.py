"""Destructive container operations (confirmation + audit required)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.errors import UNAVAILABLE, AppError
from app.core.logging import get_logger
from app.tools.registry import ToolContext, ToolSpec, registry

log = get_logger("tools.container")


def _operate(target: str, action: str) -> dict[str, Any]:
    import docker

    client = docker.from_env(timeout=10)
    container = client.containers.get(target)
    if action == "restart":
        container.restart(timeout=10)
    elif action == "stop":
        container.stop(timeout=10)
    elif action == "start":
        container.start()
    container.reload()
    return {"state": container.status, "name": container.name}


async def _run(ctx: ToolContext, action: str) -> dict[str, Any]:
    target = ctx.target_ref
    try:
        result = await asyncio.to_thread(_operate, target, action)
    except Exception as exc:  # noqa: BLE001
        log.error("容器操作失败: %s", exc, extra={"target": target, "tool": action})
        raise AppError(UNAVAILABLE, f"容器 {action} 失败：{type(exc).__name__}", 502) from exc
    label = {"restart": "重启", "stop": "停止", "start": "启动"}[action]
    return {"ok": True, "summary": f"已{label}容器 {target}，当前状态 {result['state']}", "data": result}


async def restart_container(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    return await _run(ctx, "restart")


async def stop_container(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    return await _run(ctx, "stop")


async def start_container(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    return await _run(ctx, "start")


def register() -> None:
    for action, label, handler in (
        ("restart", "重启容器", restart_container),
        ("stop", "停止容器", stop_container),
        ("start", "启动容器", start_container),
    ):
        registry.register(
            ToolSpec(
                name=f"{action}_container",
                label=label,
                description=f"{label}（破坏性操作，需要用户二次确认）。目标为当前卡片绑定的容器。",
                risk="destructive",
                kinds=["container"],
                handler=handler,
            )
        )


register()
