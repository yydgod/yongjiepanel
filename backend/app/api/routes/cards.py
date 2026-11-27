"""Card endpoints: CRUD, ordering, quick actions, metrics, logs and dsh workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.card import CardActionRequest, CardCreate, CardOut, CardUpdate, ReorderRequest
from app.services import card_service, dsh_service
from app.services.status_service import store

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("")
def list_cards(
    group: str | None = None,
    card_type: str | None = Query(default=None, alias="type"),
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "items": card_service.list_cards(db, group=group, card_type=card_type, q=q, status=status),
        "groups": card_service.groups(db),
    }


@router.post("", response_model=CardOut, status_code=201)
def create_card(payload: CardCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    return card_service.create_card(db, payload)


@router.post("/reorder")
def reorder_cards(payload: ReorderRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = [item.model_dump() for item in payload.items]
    return {"items": card_service.reorder(db, items)}


@router.get("/{card_id}")
def get_card(card_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    card = card_service.get_card(db, card_id)
    payload = card_service.serialize(card)
    payload["history"] = store.history(card_id)
    return payload


@router.patch("/{card_id}")
def update_card(card_id: str, payload: CardUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    return card_service.update_card(db, card_id, payload)


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: str, db: Session = Depends(get_db)) -> None:
    card_service.delete_card(db, card_id)


@router.post("/{card_id}/actions")
async def run_action(
    card_id: str, payload: CardActionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return await card_service.execute_quick_action(db, card_id, payload.action)


@router.get("/{card_id}/metrics")
def get_metrics(card_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    card_service.get_card(db, card_id)
    return {
        "points": store.history(card_id),
        "snapshot": store.snapshot(card_id),
    }


@router.get("/{card_id}/logs")
async def get_logs(
    card_id: str,
    lines: int = Query(default=120, ge=10, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    card = card_service.get_card(db, card_id)
    return {"lines": lines, "content": await card_service.read_logs(card, lines)}


@router.get("/{card_id}/dsh")
def dsh_workspace(card_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """解析卡片对应的 dsh 工作区，返回可直接嵌入的原生 UI 地址。"""
    card_service.get_card(db, card_id)
    store = Path(settings.dsh_cards_store).expanduser()
    if not store.exists():
        return {"configured": False, "reason": "未找到 dsh 工作区映射，请运行迁移脚本"}
    try:
        cards = json.loads(store.read_text()).get("cards") or []
    except (OSError, json.JSONDecodeError):
        return {"configured": False, "reason": "dsh 工作区映射文件无法解析"}

    entry = next((item for item in cards if item.get("card_id") == card_id), None)
    if entry is None:
        return {"configured": False, "reason": "该卡片尚未迁移为 dsh 工作区"}
    if not dsh_service.configured():
        return {"configured": False, "reason": "未配置 dsh 地址或 token"}

    return {
        "configured": True,
        "workspace_id": entry["workspace_id"],
        "title": entry.get("title"),
        "path": entry.get("path"),
        "url": dsh_service.url(entry["workspace_id"]),
    }
