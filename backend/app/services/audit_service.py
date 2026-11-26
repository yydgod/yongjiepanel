"""Audit trail service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    action: str,
    target_type: str = "card",
    target_id: str | None = None,
    params: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    actor: str = "operator",
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        params=params,
        result=result,
        error=error,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry


def serialize(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "actor": entry.actor,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "params": entry.params,
        "result": entry.result,
        "error": entry.error,
        "created_at": entry.created_at.isoformat(timespec="seconds") if entry.created_at else None,
    }


def list_logs(db: Session, limit: int = 50, action: str | None = None) -> list[dict[str, Any]]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    rows = query.order_by(desc(AuditLog.created_at)).limit(min(limit, 200)).all()
    return [serialize(row) for row in rows]
