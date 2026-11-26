"""AI card generation endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.providers import ProviderConfig
from app.db.session import get_db
from app.models import Provider
from app.schemas.generate import GenerateCardRequest, GenerateCardResponse
from app.services import provider_service
from app.services.card_generator import generate_card

router = APIRouter(prefix="/generate", tags=["generate"])


def _resolve_provider(db: Session, provider_id: str | None) -> ProviderConfig | None:
    provider: Provider | None = None
    if provider_id:
        provider = db.get(Provider, provider_id)
    if provider is None:
        provider = provider_service.default_provider(db)
    return provider_service.to_config(provider) if provider else None


@router.post("/card", response_model=GenerateCardResponse)
async def generate_card_draft(
    payload: GenerateCardRequest, db: Session = Depends(get_db)
) -> Any:
    provider = _resolve_provider(db, payload.provider_id)
    return await generate_card(payload.description, provider)
