"""Aggregated service log feed used by the dashboard homepage."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.models import ServiceCard
from app.services import card_service

router = APIRouter(tags=["logs"])
log = get_logger("logs")

# 只有容器与 systemd 单元提供日志尾部；端口 / 自定义卡片没有可读取的日志流。
LOG_CARD_TYPES = ("container", "systemd")
MAX_ITEMS = 200

_LEVEL_RE = re.compile(r"\b(fatal|critical|error|err|warn(?:ing)?|info|debug|trace)\b", re.IGNORECASE)
_ISO_TS_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_SYSLOG_TS_RE = re.compile(r"^\s*([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})")


def _level(text: str) -> str:
    match = _LEVEL_RE.search(text)
    if not match:
        return "info"
    token = match.group(1).lower()
    if token in {"fatal", "critical", "error", "err"}:
        return "error"
    if token.startswith("warn"):
        return "warn"
    if token in {"debug", "trace"}:
        return "debug"
    return "info"


def _split_timestamp(raw: str) -> tuple[str | None, str]:
    """Return a timestamp (when present in the log line) and the message."""
    iso = _ISO_TS_RE.match(raw)
    if iso:
        return iso.group(1).replace(",", "."), raw[iso.end():].strip()
    syslog = _SYSLOG_TS_RE.match(raw)
    if syslog:
        return syslog.group(1), raw[syslog.end():].strip()
    return None, raw.strip()


def _epoch(ts: str | None) -> float:
    if not ts:
        return float("-inf")
    try:
        if ts[0].isalpha():
            # syslog 时间戳缺少年份，按当前年份补齐后作为本机时间处理。
            parsed = datetime.strptime(f"{datetime.now().year} {ts}", "%Y %b %d %H:%M:%S")
        else:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return parsed.timestamp()
    except (ValueError, OverflowError):
        return float("-inf")


@router.get("/logs")
async def service_logs(
    lines: int = Query(default=60, ge=10, le=200),
    card_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the newest log lines across all log-capable, enabled cards."""
    query = db.query(ServiceCard).filter(
        ServiceCard.card_type.in_(LOG_CARD_TYPES),
        ServiceCard.enabled.is_(True),
    )
    if card_id:
        query = query.filter(ServiceCard.id == card_id)
    cards = query.order_by(ServiceCard.sort_order, ServiceCard.created_at).all()

    async def read(card: ServiceCard) -> tuple[ServiceCard, str | None, str | None]:
        try:
            return card, await card_service.read_logs(card, lines), None
        except Exception as exc:  # 单张卡片读取失败不应影响其它日志
            log.warning("读取卡片日志失败 card_id=%s error=%s", card.id, exc)
            return card, None, str(exc)

    results = await asyncio.gather(*(read(card) for card in cards))

    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for card, content, error in results:
        if error:
            errors.append({"card_id": card.id, "card_title": card.title, "message": error})
            continue
        if not content:
            continue
        for raw in reversed(content.splitlines()):
            text = raw.strip()
            if not text:
                continue
            ts, message = _split_timestamp(text)
            items.append({
                "card_id": card.id,
                "card_title": card.title,
                "card_type": card.card_type,
                "level": _level(text),
                "ts": ts,
                "message": message or text,
            })

    # 稳定排序：有时间戳的按时间倒序，无时间戳的保持原顺序并排在末尾。
    items.sort(key=lambda item: _epoch(item["ts"]), reverse=True)
    return {
        "items": items[:MAX_ITEMS],
        "cards": [
            {"id": card.id, "title": card.title, "card_type": card.card_type}
            for card in cards
        ],
        "errors": errors,
        "lines": lines,
    }
