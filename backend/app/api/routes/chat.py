"""Agent chat: SSE streaming, non-stream fallback, confirmation + history."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import INTERNAL, AppError
from app.db.session import get_db
from app.schemas.chat import ChatReply, ChatRequest, ConfirmRequest, ConfirmResult
from app.services.chat_service import chat_service

router = APIRouter(tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _pack(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/cards/{card_id}/chat", response_model=ChatReply)
async def chat(card_id: str, payload: ChatRequest) -> dict[str, Any]:
    return await chat_service.reply(card_id, payload.message, payload.session_id)


@router.post("/cards/{card_id}/chat/stream")
async def chat_stream(card_id: str, payload: ChatRequest) -> StreamingResponse:
    async def generate():  # type: ignore[no-untyped-def]
        try:
            async for event in chat_service.stream(card_id, payload.message, payload.session_id):
                yield _pack(event)
        except AppError as exc:
            yield _pack({"type": "error", "code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001
            yield _pack({"type": "error", "code": INTERNAL, "message": type(exc).__name__})
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/chat/confirm", response_model=ConfirmResult)
async def confirm_action(payload: ConfirmRequest) -> dict[str, Any]:
    return await chat_service.confirm(payload.token)


@router.get("/cards/{card_id}/sessions")
def list_sessions(card_id: str) -> dict[str, Any]:
    return {"items": chat_service.sessions(card_id)}


@router.get("/chat/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return chat_service.messages(session_id)


@router.get("/cards/{card_id}/pending")
def list_pending(card_id: str) -> dict[str, Any]:
    return {"items": chat_service.pending_for(card_id)}
