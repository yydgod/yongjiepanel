"""Generic OpenAI-compatible client (DeepSeek / Hunyuan / Qwen / local)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.errors import DENIED, NOT_CONFIGURED, TIMEOUT, UPSTREAM, AppError
from app.core.logging import get_logger

log = get_logger("ai.openai")


def _normalize_tool_calls(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in raw or []:
        function = item.get("function") or {}
        args_raw = function.get("arguments") or "{}"
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
        except json.JSONDecodeError:
            args = {"_raw": args_raw}
        calls.append(
            {
                "id": item.get("id") or f"call_{len(calls)}",
                "name": function.get("name", ""),
                "args": args,
            }
        )
    return calls


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout: float = 60.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        json_mode: bool,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

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
        if not self.api_key:
            raise AppError(NOT_CONFIGURED, "该供应商未配置 API Key", 400)
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(model, messages, temperature, max_tokens, tools, json_mode, False)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise AppError(TIMEOUT, "模型服务响应超时", 504) from exc
        except httpx.HTTPError as exc:
            raise AppError(UPSTREAM, f"无法连接模型服务：{type(exc).__name__}", 502) from exc

        if resp.status_code in (401, 403):
            raise AppError(DENIED, "API Key 被拒绝（401/403），请检查密钥", 400)
        if resp.status_code >= 400:
            raise AppError(UPSTREAM, f"模型服务返回 {resp.status_code}", 502, resp.text[:300])

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return {
            "content": message.get("content") or "",
            "tool_calls": _normalize_tool_calls(message.get("tool_calls")),
            "usage": data.get("usage") or {},
            "model": data.get("model") or model,
        }

    async def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield {"type":"text"} deltas and a final {"type":"done"} event."""
        if not self.api_key:
            raise AppError(NOT_CONFIGURED, "该供应商未配置 API Key", 400)
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(model, messages, temperature, max_tokens, tools, json_mode, True)
        buffers: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] = {}
        model_name = model
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=self._headers(), json=payload) as resp:
                    if resp.status_code in (401, 403):
                        raise AppError(DENIED, "API Key 被拒绝（401/403）", 400)
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", "ignore")[:300]
                        raise AppError(UPSTREAM, f"模型服务返回 {resp.status_code}", 502, body)
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            event = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        usage = event.get("usage") or usage
                        model_name = event.get("model") or model_name
                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if delta.get("content"):
                                yield {"type": "text", "text": delta["content"]}
                            for call in delta.get("tool_calls") or []:
                                index = int(call.get("index", 0))
                                slot = buffers.setdefault(
                                    index, {"id": "", "name": "", "arguments": ""}
                                )
                                slot["id"] = call.get("id") or slot["id"]
                                function = call.get("function") or {}
                                slot["name"] = function.get("name") or slot["name"]
                                slot["arguments"] += function.get("arguments") or ""
        except httpx.TimeoutException as exc:
            raise AppError(TIMEOUT, "模型流式响应超时", 504) from exc
        except httpx.HTTPError as exc:
            raise AppError(UPSTREAM, f"流式连接失败：{type(exc).__name__}", 502) from exc

        tool_calls = _normalize_tool_calls(
            [
                {"id": slot["id"], "function": {"name": slot["name"], "arguments": slot["arguments"]}}
                for slot in buffers.values()
                if slot["name"]
            ]
        )
        yield {"type": "done", "tool_calls": tool_calls, "usage": usage, "model": model_name}
