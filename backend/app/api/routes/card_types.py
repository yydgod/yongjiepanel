"""Card type specs — the frontend renders forms dynamically from these."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.card_types import list_card_types
from app.tools import tool_registry

router = APIRouter(prefix="/card-types", tags=["meta"])


@router.get("")
def get_card_types() -> dict[str, Any]:
    tools = [
        {"name": spec.name, "label": spec.label, "risk": spec.risk, "description": spec.description}
        for spec in tool_registry.all()
    ]
    return {"items": list_card_types(), "tools": tools}
