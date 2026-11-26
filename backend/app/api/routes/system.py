"""Health, system status, audit log and manual collection trigger."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import __version__
from app.collectors.scheduler import scheduler
from app.db.session import get_db
from app.services import audit_service, system_service

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return system_service.status(db)


@router.post("/system/collect")
async def trigger_collect() -> dict[str, Any]:
    return await scheduler.run_once()


@router.get("/audit")
def audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"items": audit_service.list_logs(db, limit=limit, action=action)}
