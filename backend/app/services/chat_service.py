"""Agent chat orchestration: streaming, tool calls, confirm tokens, audit."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.ai.gateway import GatewayRequest, gateway
from app.core.config import settings
from app.core.errors import CONFLICT, DENIED, AppError, not_found
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models import Agent, ChatMessage, ChatSession, PendingAction, ServiceCard
from app.services import agent_service, audit_service, card_service
from app.services.status_service import store
from app.tools import tool_registry

log = get_logger("chat")

MAX_HISTORY = 8
_READ_TIMEOUT_NOTE = "只读工具可直接执行；破坏性操作需要用户二次确认。"


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _system_content(card: ServiceCard, agent: Agent, snapshot: dict[str, Any] | None) -> str:
    snapshot = snapshot or {}
    metrics = []
    if snapshot.get("cpu_percent") is not None:
        metrics.append(f"CPU {snapshot['cpu_percent']}%")
    if snapshot.get("memory_mb") is not None:
        metrics.append(f"内存 {snapshot['memory_mb']} MB")
    if snapshot.get("ports"):
        metrics.append(f"端口 {snapshot['ports']}")
    lines = [
        agent.system_prompt or agent_service.default_prompt(card),
        "",
        "## 实时上下文",
        f"- 卡片：{card.title}（{card.card_type}，目标 {card.target_ref}）",
        f"- 当前状态：{snapshot.get('status', 'unknown')}",
        f"- 指标：{'；'.join(metrics) or '暂无'}",
        f"- 工具规则：{_READ_TIMEOUT_NOTE}",
    ]
    return "\n".join(lines)


def _get_or_create_session(db: Session, card: ServiceCard, agent: Agent | None, session_id: str | None, text: str) -> ChatSession:
    session = db.get(ChatSession, session_id) if session_id else None
    if session is not None and session.card_id != card.id:
        raise AppError(DENIED, "会话不属于该卡片", 400)
    if session is None:
        session = ChatSession(
            card_id=card.id,
            agent_id=agent.id if agent else None,
            title=text.strip()[:40] or "新会话",
        )
        db.add(session)
        db.flush()
    return session


def _history(db: Session, session: ChatSession) -> list[dict[str, Any]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(desc(ChatMessage.created_at))
        .limit(MAX_HISTORY)
        .all()
    )
    messages: list[dict[str, Any]] = []
    for row in reversed(rows):
        if row.role in ("user", "assistant") and row.content:
            messages.append({"role": row.role, "content": row.content})
    return messages


def _persist(
    db: Session,
    session: ChatSession,
    role: str,
    content: str,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
    channel: str | None = None,
    tokens: int = 0,
) -> None:
    db.add(
        ChatMessage(
            session_id=session.id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            channel=channel,
            tokens=tokens,
        )
    )


def _tool_payload(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call["id"],
        "type": "function",
        "function": {"name": call["name"], "arguments": json.dumps(call.get("args") or {}, ensure_ascii=False)},
    }


class ChatService:
    async def stream(
        self, card_id: str, text: str, session_id: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        with session_scope() as db:
            card = card_service.get_card(db, card_id)
            agent = card.agent
            if agent is None or not agent.enabled:
                raise AppError(CONFLICT, "该卡片未配置可用 agent", 409)
            provider = agent_service.resolve_provider_config(db, agent)
            session = _get_or_create_session(db, card, agent, session_id, text)
            _persist(db, session, "user", text)
            db.commit()

            snapshot = store.snapshot(card.id)
            allowed = [spec.name for spec in tool_registry.for_card_type(card.card_type)]
            agent_tools = [name for name in list(agent.tools or []) if name in allowed]
            if not agent_tools:
                agent_tools = ["get_status", "get_metrics"]
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": _system_content(card, agent, snapshot)},
                *_history(db, session),
            ]
            tool_schemas = tool_registry.openai_schemas(agent_tools, card.card_type)
            ctx = agent_service.context_for(card)
            channel = "direct"
            yield {"type": "session", "session_id": session.id}
            yield {"type": "tools", "tools": [s["function"]["name"] for s in tool_schemas]}

            final_text = ""
            pending: list[dict[str, Any]] = []
            for round_index in range(max(1, settings.chat_max_tool_rounds)):
                request = GatewayRequest(
                    messages=messages,
                    tools=tool_schemas or None,
                    provider=provider,
                    model=agent.model or None,
                    gateway=agent.gateway,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    session_id=session.id,
                    agent_name=agent.name,
                    card_title=card.title,
                    card_context=snapshot or {},
                )
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                usage: dict[str, Any] = {}
                async for event in gateway.stream(request):
                    kind = event.get("type")
                    if kind == "route":
                        channel = event.get("channel", channel)
                        yield {"type": "route", "channel": channel, "model": event.get("model")}
                    elif kind == "text":
                        text_parts.append(event.get("text", ""))
                        yield {"type": "delta", "text": event.get("text", "")}
                    elif kind == "done":
                        tool_calls = event.get("tool_calls") or []
                        usage = event.get("usage") or {}
                        channel = event.get("channel", channel)
                content = "".join(text_parts)
                final_text = content or final_text

                if not tool_calls:
                    _persist(
                        db,
                        session,
                        "assistant",
                        content,
                        channel=channel,
                        tokens=int(usage.get("total_tokens") or 0),
                    )
                    session.channel = channel
                    db.commit()
                    yield {
                        "type": "done",
                        "content": final_text,
                        "channel": channel,
                        "usage": usage,
                        "rounds": round_index + 1,
                    }
                    return

                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": [_tool_payload(call) for call in tool_calls],
                    }
                )
                _persist(
                    db,
                    session,
                    "assistant",
                    content,
                    tool_calls=[_tool_payload(call) for call in tool_calls],
                    channel=channel,
                )

                for call in tool_calls:
                    try:
                        spec = tool_registry.get(call["name"])
                    except AppError as exc:
                        yield {"type": "tool_result", "id": call["id"], "name": call["name"], "ok": False, "summary": exc.message}
                        messages.append(
                            {"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": json.dumps({"error": exc.message}, ensure_ascii=False)}
                        )
                        continue
                    if call["name"] not in agent_tools:
                        message = f"工具 {call['name']} 不在该 agent 的白名单内"
                        yield {"type": "tool_result", "id": call["id"], "name": call["name"], "ok": False, "summary": message}
                        messages.append(
                            {"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": json.dumps({"error": message}, ensure_ascii=False)}
                        )
                        continue

                    yield {
                        "type": "tool_call",
                        "id": call["id"],
                        "name": spec.name,
                        "label": spec.label,
                        "risk": spec.risk,
                        "args": call.get("args") or {},
                    }

                    if spec.risk == "destructive":
                        action = PendingAction(
                            card_id=card.id,
                            tool_name=spec.name,
                            params=call.get("args") or {},
                            reason=f"agent「{agent.name}」请求{spec.label}",
                            expires_at=datetime.now(UTC)
                            + timedelta(seconds=settings.confirm_token_ttl),
                        )
                        db.add(action)
                        db.commit()
                        item = {
                            "token": action.id,
                            "tool_name": spec.name,
                            "label": spec.label,
                            "params": call.get("args") or {},
                            "expires_at": _aware(action.expires_at).isoformat(timespec="seconds"),
                        }
                        pending.append(item)
                        yield {"type": "pending", **item}
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "name": call["name"],
                                "content": json.dumps({"status": "pending_user_confirmation"}, ensure_ascii=False),
                            }
                        )
                        continue

                    try:
                        result = await spec.handler(ctx, call.get("args") or {})  # type: ignore[misc]
                    except AppError as exc:
                        result = {"ok": False, "summary": exc.message, "data": None}
                    yield {
                        "type": "tool_result",
                        "id": call["id"],
                        "name": spec.name,
                        "ok": bool(result.get("ok")),
                        "summary": result.get("summary", ""),
                        "data": result.get("data"),
                    }
                    payload = json.dumps(
                        {"ok": result.get("ok"), "summary": result.get("summary"), "data": result.get("data")},
                        ensure_ascii=False,
                    )[:4000]
                    messages.append(
                        {"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": payload}
                    )
                    _persist(
                        db,
                        session,
                        "tool",
                        payload,
                        tool_call_id=call["id"],
                        tool_name=spec.name,
                        channel=channel,
                    )
                db.commit()
                if pending:
                    session.channel = channel
                    db.commit()
                    yield {
                        "type": "done",
                        "content": final_text,
                        "channel": channel,
                        "pending": pending,
                        "usage": usage,
                        "rounds": round_index + 1,
                    }
                    return

            note = "\n\n（已达到工具调用轮次上限，如需继续请再发一条消息。）"
            yield {"type": "delta", "text": note}
            _persist(db, session, "assistant", final_text + note, channel=channel)
            session.channel = channel
            db.commit()
            yield {"type": "done", "content": final_text + note, "channel": channel, "pending": []}

    async def reply(self, card_id: str, text: str, session_id: str | None = None) -> dict[str, Any]:
        content, channel, tool_events, pending, sid = "", "direct", [], [], ""
        try:
            async for event in self.stream(card_id, text, session_id):
                kind = event.get("type")
                if kind == "session":
                    sid = event["session_id"]
                elif kind == "route":
                    channel = event.get("channel", channel)
                elif kind in ("tool_call", "tool_result"):
                    tool_events.append(event)
                elif kind == "pending":
                    pending.append(event)
                elif kind == "done":
                    content = event.get("content", content)
        except AppError:
            raise
        return {
            "session_id": sid,
            "content": content,
            "channel": channel,
            "tool_calls": tool_events,
            "pending": pending,
        }

    async def confirm(self, token: str) -> dict[str, Any]:
        with session_scope() as db:
            action = db.get(PendingAction, token)
            if action is None:
                raise not_found("待确认操作", token)
            if action.status != "pending":
                raise AppError(CONFLICT, f"该操作已处理（状态：{action.status}）", 409)
            if _aware(action.expires_at) < datetime.now(UTC):
                action.status = "expired"
                db.commit()
                raise AppError(CONFLICT, "确认令牌已过期，请重新发起", 409)
            card = card_service.get_card(db, action.card_id)
            spec = tool_registry.get(action.tool_name)
            ctx = agent_service.context_for(card)
            try:
                result = await spec.handler(ctx, action.params or {})  # type: ignore[misc]
            except AppError as exc:
                action.status = "failed"
                action.result = {"error": exc.message}
                audit_service.record(
                    db,
                    action=f"tool.{spec.name}",
                    target_id=card.id,
                    params=action.params,
                    error=exc.message,
                    commit=False,
                )
                db.commit()
                return {"ok": False, "tool_name": spec.name, "status": "failed", "message": exc.message}
            action.status = "executed"
            action.result = result
            audit_service.record(
                db,
                action=f"tool.{spec.name}",
                target_id=card.id,
                params=action.params,
                result=result,
                commit=False,
            )
            db.commit()
            log.info("破坏性操作已确认执行", extra={"tool": spec.name, "card_id": card.id})
            return {
                "ok": True,
                "tool_name": spec.name,
                "status": "executed",
                "result": result,
                "message": result.get("summary", "执行成功"),
            }

    def sessions(self, card_id: str) -> list[dict[str, Any]]:
        with session_scope() as db:
            rows = (
                db.query(ChatSession)
                .filter(ChatSession.card_id == card_id)
                .order_by(desc(ChatSession.updated_at))
                .limit(20)
                .all()
            )
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "channel": row.channel,
                    "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
                }
                for row in rows
            ]

    def messages(self, session_id: str) -> dict[str, Any]:
        with session_scope() as db:
            session = db.get(ChatSession, session_id)
            if session is None:
                raise not_found("会话", session_id)
            return {
                "id": session.id,
                "card_id": session.card_id,
                "title": session.title,
                "channel": session.channel,
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "tool_calls": msg.tool_calls,
                        "tool_name": msg.tool_name,
                        "channel": msg.channel,
                        "created_at": msg.created_at.isoformat(timespec="seconds")
                        if msg.created_at
                        else None,
                    }
                    for msg in session.messages
                ],
            }

    def pending_for(self, card_id: str) -> list[dict[str, Any]]:
        with session_scope() as db:
            rows = (
                db.query(PendingAction)
                .filter(PendingAction.card_id == card_id, PendingAction.status == "pending")
                .order_by(desc(PendingAction.created_at))
                .limit(10)
                .all()
            )
            return [
                {
                    "token": row.id,
                    "tool_name": row.tool_name,
                    "params": row.params,
                    "expires_at": _aware(row.expires_at).isoformat(timespec="seconds"),
                }
                for row in rows
            ]


chat_service = ChatService()
