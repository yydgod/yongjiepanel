"""Card CRUD, ordering, filtering and quick actions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import DENIED, AppError, not_found
from app.db.base import utcnow
from app.models import Agent, Host, ServiceCard
from app.schemas.card import CardCreate, CardUpdate
from app.services import agent_service, audit_service
from app.services.card_types import default_display_config, get_card_type, tools_for
from app.services.status_service import store
from app.tools import tool_registry

UNKNOWN_STATUS: dict[str, Any] = {
    "status": "unknown",
    "cpu_percent": None,
    "memory_mb": None,
    "uptime_seconds": None,
    "ports": [],
    "detail": "等待首次采集",
    "error": None,
}


def ensure_local_host(db: Session) -> Host:
    host = db.query(Host).filter(Host.kind == "local").first()
    if host is None:
        host = Host(name="本机", kind="local", status="online", last_seen=utcnow())
        db.add(host)
        db.flush()
    return host


def get_card(db: Session, card_id: str) -> ServiceCard:
    card = db.get(ServiceCard, card_id)
    if card is None:
        raise not_found("卡片", card_id)
    return card


def serialize(card: ServiceCard, with_status: bool = True) -> dict[str, Any]:
    snapshot = store.snapshot(card.id) if with_status else None
    return {
        "id": card.id,
        "host_id": card.host_id,
        "title": card.title,
        "subtitle": card.subtitle,
        "card_type": card.card_type,
        "target_ref": card.target_ref,
        "group_name": card.group_name,
        "icon": card.icon,
        "accent": card.accent,
        "sort_order": card.sort_order,
        "display_config": dict(card.display_config or {}),
        "enabled": card.enabled,
        "agent": agent_service.serialize(card.agent),
        "status": snapshot or {**UNKNOWN_STATUS, "collector": card.card_type},
        "created_at": card.created_at.isoformat(timespec="seconds") if card.created_at else None,
        "updated_at": card.updated_at.isoformat(timespec="seconds") if card.updated_at else None,
    }


def list_cards(
    db: Session,
    *,
    group: str | None = None,
    card_type: str | None = None,
    q: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = db.query(ServiceCard)
    if group:
        query = query.filter(ServiceCard.group_name == group)
    if card_type:
        query = query.filter(ServiceCard.card_type == card_type)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (ServiceCard.title.like(like))
            | (ServiceCard.target_ref.like(like))
            | (ServiceCard.subtitle.like(like))
        )
    rows = query.order_by(ServiceCard.sort_order, ServiceCard.created_at).all()
    cards = [serialize(row) for row in rows]
    if status:
        cards = [card for card in cards if card["status"].get("status") == status]
    return cards


def groups(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(ServiceCard.group_name, func.count(ServiceCard.id))
        .group_by(ServiceCard.group_name)
        .order_by(ServiceCard.group_name)
        .all()
    )
    return [{"name": name, "count": count} for name, count in rows]


def create_card(db: Session, payload: CardCreate) -> dict[str, Any]:
    spec = get_card_type(payload.card_type)
    if spec is None:
        raise AppError("validation", f"未知卡片类型：{payload.card_type}", 422)
    host = db.get(Host, payload.host_id) if payload.host_id else ensure_local_host(db)
    max_order = db.query(func.max(ServiceCard.sort_order)).scalar() or 0
    card = ServiceCard(
        host_id=host.id if host else ensure_local_host(db).id,
        title=payload.title,
        subtitle=payload.subtitle,
        card_type=payload.card_type,
        target_ref=payload.target_ref,
        group_name=payload.group_name or "默认分组",
        icon=payload.icon or spec["icon"],
        accent=payload.accent or spec["accent"],
        sort_order=payload.sort_order if payload.sort_order is not None else max_order + 10,
        display_config={**default_display_config(payload.card_type), **(payload.display_config or {})},
        enabled=payload.enabled,
    )
    db.add(card)
    db.flush()
    agent = agent_service.build_agent(db, card, payload.agent)
    db.add(agent)
    db.commit()
    db.refresh(card)
    audit_service.record(
        db,
        action="card.create",
        target_id=card.id,
        params={"title": card.title, "type": card.card_type},
    )
    return serialize(card)


def update_card(db: Session, card_id: str, payload: CardUpdate) -> dict[str, Any]:
    card = get_card(db, card_id)
    data = payload.model_dump(exclude_unset=True, exclude={"agent"})
    if "card_type" in data and data["card_type"] != card.card_type:
        if get_card_type(data["card_type"]) is None:
            raise AppError("validation", f"未知卡片类型：{data['card_type']}", 422)
        card.display_config = {
            **default_display_config(data["card_type"]),
            **dict(card.display_config or {}),
        }
    for field, value in data.items():
        if value is not None or field == "subtitle":
            setattr(card, field, value)
    if payload.agent is not None:
        if card.agent is None:
            db.add(agent_service.build_agent(db, card, payload.agent))
        else:
            agent_service.apply_agent_update(card.agent, payload.agent, card)
    card.updated_at = utcnow()
    db.commit()
    db.refresh(card)
    return serialize(card)


def delete_card(db: Session, card_id: str) -> None:
    card = get_card(db, card_id)
    db.delete(card)
    db.commit()
    audit_service.record(db, action="card.delete", target_id=card_id)


def reorder(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [item["id"] for item in items]
    cards = {card.id: card for card in db.query(ServiceCard).filter(ServiceCard.id.in_(ids)).all()}
    for item in items:
        card = cards.get(item["id"])
        if card is not None:
            card.sort_order = int(item["sort_order"])
    db.commit()
    return list_cards(db)


async def execute_quick_action(db: Session, card_id: str, action: str) -> dict[str, Any]:
    card = get_card(db, card_id)
    tool_name = {
        ("container", "restart"): "restart_container",
        ("container", "stop"): "stop_container",
        ("container", "start"): "start_container",
        ("systemd", "restart"): "restart_unit",
    }.get((card.card_type, action))
    if tool_name is None:
        raise AppError(
            DENIED,
            f"{card.card_type} 类型卡片不支持「{action}」操作，请在详情页使用 agent 处理",
            400,
        )
    spec = tool_registry.get(tool_name)
    ctx = agent_service.context_for(card)
    try:
        result = await spec.handler(ctx, {})  # type: ignore[misc]
    except AppError as exc:
        audit_service.record(
            db,
            action=f"card.{action}",
            target_id=card.id,
            params={"tool": tool_name},
            error=exc.message,
        )
        raise
    audit_service.record(
        db,
        action=f"card.{action}",
        target_id=card.id,
        params={"tool": tool_name},
        result=result.get("data"),
    )
    return result


def agent_tools_available(card: ServiceCard) -> list[str]:
    """Union of registry tools valid for this card type (used by the UI)."""
    valid = {spec.name for spec in tool_registry.for_card_type(card.card_type)}
    return [name for name in tools_for(card.card_type) if name in valid]


def agent_for(db: Session, card_id: str) -> Agent | None:
    card = get_card(db, card_id)
    return card.agent
