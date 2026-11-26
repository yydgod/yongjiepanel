"""Card endpoints: CRUD, ordering, quick actions, metrics, logs, agent config."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.card import (
    AgentConfigIn,
    CardActionRequest,
    CardCreate,
    CardOut,
    CardUpdate,
    ReorderRequest,
)
from app.services import agent_service, card_generator, card_service, provider_service
from app.services.status_service import store
from app.tools import tool_registry

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
    payload["available_tools"] = [
        {"name": spec.name, "label": spec.label, "risk": spec.risk, "description": spec.description}
        for spec in tool_registry.for_card_type(card.card_type)
    ]
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
    spec = tool_registry.get("tail_logs")
    if card.card_type not in spec.kinds:
        raise AppError("unavailable", f"{card.card_type} 类型卡片暂不支持日志读取", 400)
    result = await spec.handler(agent_service.context_for(card), {"lines": lines})  # type: ignore[misc]
    return {"lines": lines, "content": (result.get("data") or {}).get("logs", "")}


@router.get("/{card_id}/agent")
def get_agent(card_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    card = card_service.get_card(db, card_id)
    provider = agent_service.resolve_provider_config(db, card.agent)
    return {
        "agent": agent_service.serialize(card.agent),
        "provider": (
            {"id": provider.id, "name": provider.name, "model": provider.default_model, "ready": provider.usable}
            if provider
            else None
        ),
    }


@router.put("/{card_id}/agent")
def update_agent(
    card_id: str, payload: AgentConfigIn, db: Session = Depends(get_db)
) -> dict[str, Any]:
    card = card_service.get_card(db, card_id)
    if card.agent is None:
        card_service.update_card(db, card_id, CardUpdate(agent=payload))
    else:
        agent_service.apply_agent_update(card.agent, payload, card)
        db.commit()
    updated = card_service.get_card(db, card_id)
    return {"agent": agent_service.serialize(updated.agent)}


@router.post("/{card_id}/customize")
def customize_card(
    card_id: str, payload: dict[str, str], db: Session = Depends(get_db)
) -> dict[str, Any]:
    card = card_service.get_card(db, card_id)
    instruction = (payload.get("instruction") or "").strip()
    if not instruction:
        raise AppError("validation", "instruction 不能为空", 422)
    result = card_generator.customize_card(card, instruction)
    return result.model_dump()


@router.get("/{card_id}/providers")
def providers_for_agent(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"items": provider_service.list_providers(db)}
