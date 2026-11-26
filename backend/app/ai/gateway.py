"""Single AI exit point: OpenClaw-first routing with graceful degradation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.ai import openclaw_client
from app.ai.mock_client import MockClient
from app.ai.openai_compat import OpenAICompatClient
from app.ai.providers import ProviderConfig
from app.core.config import settings
from app.core.errors import NOT_CONFIGURED, TIMEOUT, UPSTREAM, AppError
from app.core.logging import get_logger

log = get_logger("ai.gateway")


@dataclass(slots=True)
class GatewayRequest:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    provider: ProviderConfig | None = None
    model: str | None = None
    gateway: str = "auto"  # auto | openclaw | direct
    temperature: float = 0.3
    max_tokens: int = 1024
    json_mode: bool = False
    session_id: str = "default"
    agent_name: str = "card-agent"
    card_title: str = ""
    card_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GatewayResult:
    content: str
    tool_calls: list[dict[str, Any]]
    usage: dict[str, Any]
    channel: str
    model: str


class AIGateway:
    def _direct_client(self, provider: ProviderConfig) -> OpenAICompatClient:
        headers: dict[str, str] = {}
        if provider.kind == "hunyuan":
            headers["X-Source"] = "yongjie-panel"
        return OpenAICompatClient(
            base_url=provider.base_url,
            api_key=provider.api_key,
            timeout=provider.timeout or settings.llm_timeout,
            extra_headers=headers,
        )

    async def resolve(self, req: GatewayRequest) -> tuple[Any, str, str]:
        model = req.provider.model_or(req.model) if req.provider else (req.model or "mock")
        wants_openclaw = req.gateway in ("auto", "openclaw")
        if wants_openclaw and openclaw_client.configured():
            healthy, reason = await openclaw_client.health()
            if healthy:
                client = openclaw_client.build_client(
                    session_id=req.session_id, agent_name=req.agent_name
                )
                return client, "openclaw", model
            log.warning("OpenClaw 不可用，尝试降级: %s", reason, extra={"channel": "openclaw"})
            if req.gateway == "openclaw":
                log.info("agent 强制 openclaw 但探测失败，继续降级直连")

        if req.provider and req.provider.usable:
            return self._direct_client(req.provider), "direct", model

        if settings.allow_mock_ai:
            return MockClient(req.card_title, req.card_context), "mock", "mock"

        raise AppError(
            NOT_CONFIGURED,
            "未配置可用的 AI 通道：请配置供应商 API Key，或启动 OpenClaw 网关（ALLOW_MOCK_AI=true 可启用演示通道）",
            400,
        )

    async def chat(self, req: GatewayRequest) -> GatewayResult:
        client, channel, model = await self.resolve(req)
        try:
            raw = await client.chat(
                model=model,
                messages=req.messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                tools=req.tools,
                json_mode=req.json_mode,
            )
        except AppError as exc:
            if channel == "openclaw" and req.provider and req.provider.usable:
                log.warning("OpenClaw 调用失败，降级直连: %s", exc.message, extra={"channel": "fallback"})
                client, channel, model = self._direct_client(req.provider), "fallback", model
                raw = await client.chat(
                    model=model,
                    messages=req.messages,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    tools=req.tools,
                    json_mode=req.json_mode,
                )
            elif settings.allow_mock_ai and exc.code in (UPSTREAM, TIMEOUT):
                client, channel, model = MockClient(req.card_title, req.card_context), "mock", "mock"
                raw = await client.chat(
                    model=model,
                    messages=req.messages,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    tools=req.tools,
                    json_mode=req.json_mode,
                )
            else:
                raise
        return GatewayResult(
            content=raw.get("content", ""),
            tool_calls=raw.get("tool_calls") or [],
            usage=raw.get("usage") or {},
            channel=channel,
            model=raw.get("model") or model,
        )

    async def stream(self, req: GatewayRequest) -> AsyncIterator[dict[str, Any]]:
        client, channel, model = await self.resolve(req)
        yield {"type": "route", "channel": channel, "model": model}
        try:
            async for event in client.stream(
                model=model,
                messages=req.messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                tools=req.tools,
                json_mode=req.json_mode,
            ):
                if event.get("type") == "done":
                    event["channel"] = channel
                yield event
        except AppError as exc:
            if channel == "openclaw" and req.provider and req.provider.usable:
                log.warning("流式降级直连: %s", exc.message, extra={"channel": "fallback"})
                direct = self._direct_client(req.provider)
                yield {"type": "route", "channel": "fallback", "model": model}
                async for event in direct.stream(
                    model=model,
                    messages=req.messages,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    tools=req.tools,
                    json_mode=req.json_mode,
                ):
                    if event.get("type") == "done":
                        event["channel"] = "fallback"
                    yield event
            elif settings.allow_mock_ai and exc.code in (UPSTREAM, TIMEOUT):
                mock = MockClient(req.card_title, req.card_context)
                yield {"type": "route", "channel": "mock", "model": "mock"}
                async for event in mock.stream(messages=req.messages, tools=req.tools):
                    if event.get("type") == "done":
                        event["channel"] = "mock"
                    yield event
            else:
                raise

    async def structured(
        self, req: GatewayRequest, schema_hint: str
    ) -> tuple[dict[str, Any] | None, str]:
        """Ask for strict JSON; retry once when the model emits invalid JSON."""
        req.json_mode = True
        req.messages = [
            {
                "role": "system",
                "content": "你是结构化数据生成器，只输出符合给定 JSON Schema 的 JSON，不要任何解释或代码块。\n"
                + schema_hint,
            },
            *[m for m in req.messages if m.get("role") != "system"],
        ]
        last_error = ""
        for attempt in range(2):
            result = await self.chat(req)
            if result.channel == "mock":
                return None, "mock"
            text = result.content.strip().strip("`")
            if text.startswith("json"):
                text = text[4:]
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed, result.channel
                last_error = "JSON 顶层不是对象"
            except json.JSONDecodeError as exc:
                last_error = str(exc)
            log.warning("结构化输出解析失败 attempt=%s: %s", attempt + 1, last_error)
            req.messages.append({"role": "assistant", "content": result.content})
            req.messages.append(
                {"role": "user", "content": f"上一条输出不是合法 JSON（{last_error}），请只输出 JSON。"}
            )
        raise AppError(UPSTREAM, "模型未能输出合法 JSON", 502, last_error)


gateway = AIGateway()
