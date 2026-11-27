"""Terminal sessions: run shell commands and inspect persistent history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.terminal import TerminalCreateRequest, TerminalExecRequest
from app.services import audit_service, terminal_service

router = APIRouter(prefix="/terminal", tags=["terminal"])


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    return terminal_service.list_sessions()


@router.post("/sessions", status_code=201)
def create_session(
    payload: TerminalCreateRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    result = terminal_service.create_session(payload.title)
    audit_service.record(
        db,
        action="terminal.create",
        target_type="terminal",
        target_id=result["id"],
        params={"title": result["title"]},
    )
    return result


@router.delete("/sessions/{session_id}", status_code=204)
def close_session(session_id: str, db: Session = Depends(get_db)) -> None:
    terminal_service.close_session(session_id)
    audit_service.record(
        db,
        action="terminal.close",
        target_type="terminal",
        target_id=session_id,
    )


@router.post("/exec")
def exec_command(payload: TerminalExecRequest) -> dict[str, Any]:
    return terminal_service.exec_command(
        payload.session_id, payload.command, payload.timeout
    )


@router.get("/history")
def history(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return terminal_service.history(limit)


@router.delete("/history", status_code=204)
def clear_history() -> None:
    terminal_service.clear_history()
