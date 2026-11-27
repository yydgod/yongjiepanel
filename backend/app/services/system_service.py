"""System status aggregation for the dashboard header and system page."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.collectors.registry import registry
from app.core.config import settings
from app.models import ServiceCard
from app.services.status_service import store


def status(db: Session) -> dict[str, Any]:
    collectors = store.diagnostics() or registry.diagnostics()
    return {
        "overview": store.overview(),
        "scheduler": store.health(),
        "collectors": collectors,
        "cards_total": db.query(ServiceCard).count(),
        "interval": settings.collect_interval,
    }
