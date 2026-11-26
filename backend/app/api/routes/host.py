"""Host overview endpoints: realtime snapshot plus rolling history."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.host_monitor import host_monitor

router = APIRouter(prefix="/host", tags=["host"])


@router.get("/overview")
def overview() -> dict:
    """Current host snapshot with the last N samples for trend charts."""
    return host_monitor.snapshot()


@router.post("/sample")
async def sample() -> dict:
    """Force an immediate sample (used by the refresh button / tests)."""
    return await host_monitor.force_sample()
