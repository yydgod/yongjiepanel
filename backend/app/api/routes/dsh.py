"""dsh 原生工作区入口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services import dsh_service

router = APIRouter(prefix="/dsh", tags=["dsh"])


@router.get("")
def dsh_entry() -> dict[str, Any]:
    """返回 dsh 原生 UI 地址（不含具体工作区，由 dsh 自己选择）。"""
    return dsh_service.entry()
