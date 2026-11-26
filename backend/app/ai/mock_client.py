"""Offline demo channel so the dashboard is usable without any API key."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger

log = get_logger("ai.mock")

_WORD_DELAY = 0.018


class MockClient:
    """Deterministic assistant used when no provider key / gateway is available."""

    def __init__(self, card_title: str = "", card_context: dict[str, Any] | None = None) -> None:
        self.card_title = card_title
        self.context = card_context or {}

    def _compose(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> str:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        )
        status = self.context.get("status") or "unknown"
        cpu = self.context.get("cpu_percent")
        mem = self.context.get("memory_mb")
        parts = [
            "【演示通道】未配置可用的大模型 API Key，以下是基于本地采集数据的回答。\n\n",
            f"关于「{self.card_title or '当前卡片'}」：当前状态为 {status}",
        ]
        if cpu is not None:
            parts.append(f"，CPU 约 {cpu}%")
        if mem is not None:
            parts.append(f"，内存约 {mem} MB")
        parts.append("。\n")
        if tools:
            names = "、".join(tool["function"]["name"] for tool in tools)
            parts.append(f"我可调用的工具：{names}。\n")
        if "重启" in last_user or "restart" in last_user.lower():
            parts.append("\n如需重启，请在工具调用确认卡片中二次确认，我会记录到审计日志。")
        elif "日志" in last_user:
            parts.append("\n你可以在右侧「日志」标签查看尾部输出，或让我调用 tail_logs 拉取。")
        else:
            parts.append(f"\n你的问题：「{last_user[:120]}」。配置 DeepSeek / 混元 / Qwen 的 API Key 后即可获得真实模型推理。")
        return "".join(parts)

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
        if json_mode:
            payload = {
                "title": "演示草稿",
                "subtitle": "由离线演示通道生成",
                "card_type": "container",
                "target_ref": "",
                "group_name": "AI 生成",
                "icon": "sparkles",
                "accent": "teal",
                "display_config": {},
                "system_prompt": "",
                "tools": [],
                "rationale": "离线演示通道无法调用真实模型，请配置 API Key 以获得可用草稿。",
            }
            content = json.dumps(payload, ensure_ascii=False)
        else:
            content = self._compose(messages, tools)
        return {"content": content, "tool_calls": [], "usage": {}, "model": "mock"}

    async def stream(self, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        text = self._compose(kwargs.get("messages") or [], kwargs.get("tools"))
        for index in range(0, len(text), 6):
            yield {"type": "text", "text": text[index : index + 6]}
            await asyncio.sleep(_WORD_DELAY)
        yield {"type": "done", "tool_calls": [], "usage": {}, "model": "mock"}
