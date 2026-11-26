"""Agent ↔ provider resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.providers import ProviderConfig
from app.models import Agent, Provider, ServiceCard
from app.schemas.card import AgentConfigIn
from app.services import provider_service


@dataclass(slots=True)
class CardCtx:
    """Lightweight ToolContext implementation (avoids exposing the ORM)."""

    card_id: str
    card_type: str
    target_ref: str
    title: str


def default_prompt(card: ServiceCard) -> str:
    return (
        f"你是服务器卡片「{card.title}」的专属运维助手，负责监控与诊断 {card.card_type} "
        f"目标「{card.target_ref}」。\n"
        "原则：先调用只读工具确认事实再下结论；涉及重启/停止等破坏性操作必须先说明影响并等待用户确认；"
        "回答保持简短，使用中文，给出可执行的下一步建议。"
    )


def build_agent(db: Session, card: ServiceCard, cfg: AgentConfigIn | None) -> Agent:
    from app.services.card_types import tools_for

    cfg = cfg or AgentConfigIn()
    provider = None
    if cfg.provider_id:
        provider = db.get(Provider, cfg.provider_id)
    if provider is None:
        provider = provider_service.default_provider(db)
    return Agent(
        card_id=card.id,
        name=cfg.name,
        provider_id=provider.id if provider else None,
        model=cfg.model or (provider.default_model if provider else ""),
        system_prompt=cfg.system_prompt or default_prompt(card),
        tools=cfg.tools or tools_for(card.card_type),
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        gateway=cfg.gateway,
        enabled=cfg.enabled,
    )


def apply_agent_update(agent: Agent, cfg: AgentConfigIn, card: ServiceCard) -> Agent:
    agent.name = cfg.name
    agent.provider_id = cfg.provider_id
    agent.model = cfg.model
    agent.system_prompt = cfg.system_prompt or default_prompt(card)
    agent.tools = cfg.tools
    agent.temperature = cfg.temperature
    agent.max_tokens = cfg.max_tokens
    agent.gateway = cfg.gateway
    agent.enabled = cfg.enabled
    return agent


def resolve_provider_config(db: Session, agent: Agent | None) -> ProviderConfig | None:
    if agent is None:
        return None
    provider: Provider | None = None
    if agent.provider_id:
        provider = db.get(Provider, agent.provider_id)
    if provider is None or not provider.enabled:
        provider = provider_service.default_provider(db)
    return provider_service.to_config(provider) if provider else None


def serialize(agent: Agent | None) -> dict[str, Any] | None:
    if agent is None:
        return None
    return {
        "id": agent.id,
        "card_id": agent.card_id,
        "name": agent.name,
        "provider_id": agent.provider_id,
        "model": agent.model,
        "system_prompt": agent.system_prompt,
        "tools": list(agent.tools or []),
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "gateway": agent.gateway,
        "enabled": agent.enabled,
    }


def context_for(card: ServiceCard) -> CardCtx:
    return CardCtx(
        card_id=card.id,
        card_type=card.card_type,
        target_ref=card.target_ref,
        title=card.title,
    )
