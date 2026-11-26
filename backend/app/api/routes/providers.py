"""Provider management + OpenClaw gateway status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import openclaw_client
from app.db.session import get_db
from app.schemas.provider import ProviderIn, ProviderOut, ProviderPreset, ProviderTestResult
from app.services import provider_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return provider_service.list_providers(db)


@router.get("/presets", response_model=list[ProviderPreset])
def presets() -> list[dict[str, Any]]:
    return provider_service.presets()


@router.get("/openclaw")
async def openclaw_status(force: bool = False) -> dict[str, Any]:
    healthy, reason = await openclaw_client.health(force=force)
    return {**openclaw_client.status(), "healthy": healthy, "reason": reason}


@router.post("", response_model=ProviderOut, status_code=201)
def create_provider(payload: ProviderIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return provider_service.create_provider(db, payload)


@router.put("/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: str, payload: ProviderIn, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return provider_service.update_provider(db, provider_id, payload)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(provider_id: str, db: Session = Depends(get_db)) -> None:
    provider_service.delete_provider(db, provider_id)


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(provider_id: str, db: Session = Depends(get_db)) -> ProviderTestResult:
    return await provider_service.test_provider(db, provider_id)
