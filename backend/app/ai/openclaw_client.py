"""OpenClaw gateway client.

Two modes:
- ``openai``  : the gateway exposes an OpenAI-compatible endpoint (default)
- ``channel`` : the gateway exposes a channel/message endpoint (session based)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.ai.openai_compat import OpenAICompatClient
from app.core.config import settings
from app.core.errors import TIMEOUT, UPSTREAM, AppError
from app.core.logging import get_logger

log = get_logger("ai.openclaw")

_HEALTH_TTL = 30
_health_cache: dict[str, Any] = {"ok": False, "at": 0.0, "reason": "未配置"}


def _base() -> str:
    return settings.openclaw_base_url.rstrip("/")


def configured() -> bool:
    return bool(_base())


async def health(force: bool = False) -> tuple[bool, str]:
    """Cached health probe so every chat call does not pay for an extra RTT."""
    if not configured():
        return False, "未配置 OPENCLAW_BASE_URL"
    now = time.time()
    if not force and now - float(_health_cache["at"]) < _HEALTH_TTL:
        return bool(_health_cache["ok"]), str(_health_cache["reason"])

    ok, reason = False, ""
    headers = {"Accept": "application/json"}
    if settings.openclaw_token:
        headers["Authorization"] = f"Bearer {settings.openclaw_token}"
    for path in ("/health", "/v1/models", "/"):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{_base()}{path}", headers=headers)
            if resp.status_code < 500:
                ok, reason = True, ""
                break
            reason = f"{path} 返回 {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            reason = f"{type(exc).__name__}: {exc}"[:160]
    _health_cache.update({"ok": ok, "at": now, "reason": reason})
    return ok, reason


def status() -> dict[str, Any]:
    return {
        "configured": configured(),
        "base_url": _base() or None,
        "mode": settings.openclaw_mode,
        "healthy": bool(_health_cache["ok"]),
        "reason": _health_cache["reason"],
        "checked_at": float(_health_cache["at"]) or None,
    }


def build_client(*, session_id: str, agent_name: str) -> Any:
    if settings.openclaw_mode == "channel":
        return OpenClawChannelClient(base_url=_base(), session_id=session_id, agent_name=agent_name)
    headers = {"X-OpenClaw-Session": session_id, "X-OpenClaw-Agent": agent_name}
    if settings.openclaw_token:
        headers["X-OpenClaw-Token"] = settings.openclaw_token
    return OpenAICompatClient(
        base_url=f"{_base()}/v1",
        api_key=settings.openclaw_token or "openclaw",
        timeout=settings.llm_timeout,
        extra_headers=headers,
    )


class OpenClawChannelClient:
    """Channel mode adapter — normalizes to the same chat/stream contract."""

    def __init__(self, base_url: str, session_id: str, agent_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.agent_name = agent_name

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        )
        payload = {
            "session": self.session_id,
            "agent": self.agent_name,
            "text": last_user,
            "model": model,
            "tools": tools or [],
            "json_mode": json_mode,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if settings.openclaw_token:
            headers["Authorization"] = f"Bearer {settings.openclaw_token}"
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/channel/message", headers=headers, json=payload
                )
        except httpx.TimeoutException as exc:
            raise AppError(TIMEOUT, "OpenClaw 网关响应超时", 504) from exc
        except httpx.HTTPError as exc:
            raise AppError(UPSTREAM, f"OpenClaw 网关连接失败：{type(exc).__name__}", 502) from exc
        if resp.status_code >= 400:
            raise AppError(UPSTREAM, f"OpenClaw 网关返回 {resp.status_code}", 502, resp.text[:300])
        data = resp.json()
        calls = data.get("tool_calls") or []
        return {
            "content": data.get("content") or data.get("reply") or "",
            "tool_calls": [
                {"id": c.get("id", f"call_{i}"), "name": c.get("name", ""), "args": c.get("args", {})}
                for i, c in enumerate(calls)
            ],
            "usage": data.get("usage") or {},
            "model": data.get("model") or model,
        }

    async def stream(self, **kwargs: Any):  # type: ignore[no-untyped-def]
        result = await self.chat(**kwargs)
        if result["content"]:
            yield {"type": "text", "text": result["content"]}
        yield {
            "type": "done",
            "tool_calls": result["tool_calls"],
            "usage": result["usage"],
            "model": result["model"],
        }
