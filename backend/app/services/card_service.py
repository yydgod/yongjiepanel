"""Card CRUD, ordering, filtering and quick actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import DENIED, AppError, not_found
from app.core.logging import get_logger
from app.db.base import utcnow
from app.models import Host, ServiceCard
from app.schemas.card import CardCreate, CardUpdate
from app.services import audit_service, dsh_service, file_service
from app.services.card_types import default_display_config, get_card_type
from app.services.status_service import store
from app.tools import tool_registry

log = get_logger("cards")

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


def _normalize_workspace_path(raw: str | None) -> tuple[str | None, Path | None]:
    if raw is None or not raw.strip():
        return None, None
    target = file_service.resolve(raw.strip())
    if not target.exists():
        raise AppError("validation", f"工作区目录不存在: {raw.strip()}", 400)
    if not target.is_dir():
        raise AppError("validation", "工作区目录必须是目录", 400)
    return file_service.relative(target), target


def _workspace_payload(card: ServiceCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "title": card.title,
        "icon": card.icon,
        "accent": card.accent,
        "group_name": card.group_name,
        "card_type": card.card_type,
        "target_ref": card.target_ref,
    }


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
        "workspace_path": card.workspace_path,
        "icon": card.icon,
        "accent": card.accent,
        "sort_order": card.sort_order,
        "display_config": dict(card.display_config or {}),
        "enabled": card.enabled,
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
    workspace_path, workspace_target = _normalize_workspace_path(payload.workspace_path)
    card = ServiceCard(
        host_id=host.id if host else ensure_local_host(db).id,
        title=payload.title,
        subtitle=payload.subtitle,
        card_type=payload.card_type,
        target_ref=payload.target_ref,
        group_name=payload.group_name or "默认分组",
        workspace_path=workspace_path,
        icon=payload.icon or spec["icon"],
        accent=payload.accent or spec["accent"],
        sort_order=payload.sort_order if payload.sort_order is not None else max_order + 10,
        display_config={**default_display_config(payload.card_type), **(payload.display_config or {})},
        enabled=payload.enabled,
    )
    db.add(card)
    db.flush()
    if workspace_path is not None:
        dsh_service.bind_card(_workspace_payload(card), workspace_path)
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
    data = payload.model_dump(exclude_unset=True)
    workspace_changed = "workspace_path" in data
    workspace_raw = data.pop("workspace_path", None)
    workspace_path, workspace_target = (
        _normalize_workspace_path(workspace_raw) if workspace_changed else (None, None)
    )
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
    if workspace_changed and workspace_path != card.workspace_path:
        card.workspace_path = workspace_path
        if workspace_path is not None:
            dsh_service.bind_card(_workspace_payload(card), workspace_path)
        else:
            dsh_service.unbind_card(card.id)
    card.updated_at = utcnow()
    db.commit()
    db.refresh(card)
    return serialize(card)


def delete_card(db: Session, card_id: str) -> None:
    card = get_card(db, card_id)
    try:
        dsh_service.unbind_card(card.id)
    except AppError as exc:
        log.warning("移除 dsh 卡片映射失败 %s: %s", card_id, exc.message)
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
            f"{card.card_type} 类型卡片不支持「{action}」操作，请在 dsh 工作区中处理",
            400,
        )
    spec = tool_registry.get(tool_name)
    ctx = _tool_context(card)
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


class _ToolContext:
    """Minimal view of a card consumed by quick-action tools."""

    def __init__(self, card: ServiceCard) -> None:
        self.card_id = card.id
        self.card_type = card.card_type
        self.target_ref = card.target_ref
        self.title = card.title


def _tool_context(card: ServiceCard) -> _ToolContext:
    return _ToolContext(card)


async def read_logs(card: ServiceCard, lines: int) -> str:
    """Read tail logs for containers and systemd units without an agent."""
    import asyncio
    import subprocess

    def _container() -> str:
        import docker

        client = docker.from_env(timeout=5)
        return client.containers.get(card.target_ref).logs(tail=lines).decode("utf-8", "ignore")

    def _unit() -> str:
        proc = subprocess.run(
            ["journalctl", "-u", card.target_ref, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return proc.stdout or proc.stderr

    if card.card_type == "container":
        return await asyncio.to_thread(_container)
    if card.card_type == "systemd":
        return await asyncio.to_thread(_unit)
    raise AppError("unavailable", f"{card.card_type} 类型卡片暂不支持日志读取", 400)
