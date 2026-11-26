"""System status aggregation for the dashboard header and system page."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ai import openclaw_client
from app.collectors.registry import registry
from app.core.config import settings
from app.models import Provider, ServiceCard
from app.services.status_service import store


def status(db: Session) -> dict[str, Any]:
    collectors = store.diagnostics() or registry.diagnostics()
    providers = db.query(Provider).all()
    return {
        "overview": store.overview(),
        "scheduler": store.health(),
        "collectors": collectors,
        "openclaw": {
            **openclaw_client.status(),
            "mode": settings.openclaw_mode,
            "configured": openclaw_client.configured(),
        },
        "ai": {
            "providers_total": len(providers),
            "providers_ready": sum(1 for p in providers if p.api_key_encrypted),
            "mock_enabled": settings.allow_mock_ai,
        },
        "cards_total": db.query(ServiceCard).count(),
        "interval": settings.collect_interval,
    }
