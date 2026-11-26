"""Destructive systemd operations — argv whitelist only, never a shell string."""

from __future__ import annotations

import asyncio
import re
import subprocess
from typing import Any

from app.core.errors import DENIED, UNAVAILABLE, AppError
from app.core.logging import get_logger
from app.tools.registry import ToolContext, ToolSpec, registry

log = get_logger("tools.systemd")

UNIT_RE = re.compile(r"^[A-Za-z0-9@._:\-]{1,120}$")


def _systemctl(action: str, unit: str) -> dict[str, Any]:
    if not UNIT_RE.match(unit):
        raise AppError(DENIED, "unit 名称包含非法字符", 400)
    proc = subprocess.run(
        ["systemctl", action, unit], capture_output=True, text=True, timeout=20, check=False
    )
    if proc.returncode != 0:
        raise AppError(
            UNAVAILABLE, f"systemctl {action} 失败：{(proc.stderr or '').strip()[:160]}", 502
        )
    return {"unit": unit, "action": action, "stdout": (proc.stdout or "").strip()}


async def restart_unit(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    unit = str(args.get("unit") or ctx.target_ref)
    result = await asyncio.to_thread(_systemctl, "restart", unit)
    return {"ok": True, "summary": f"已重启 systemd 服务 {unit}", "data": result}


def register() -> None:
    registry.register(
        ToolSpec(
            name="restart_unit",
            label="重启服务",
            description="重启当前卡片绑定的 systemd unit（破坏性操作，需要用户二次确认）。",
            risk="destructive",
            kinds=["systemd"],
            params={"unit": {"type": "string", "description": "可选，覆盖默认 unit"}},
            handler=restart_unit,
        )
    )


register()
