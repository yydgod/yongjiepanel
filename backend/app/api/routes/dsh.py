"""dsh 原生工作区入口与工作区创建。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dsh import WorkspaceBootstrapRequest, WorkspaceCreateRequest
from app.services import audit_service, dsh_service

router = APIRouter(prefix="/dsh", tags=["dsh"])


@router.get("")
def dsh_entry() -> dict[str, Any]:
    """返回 dsh 原生 UI 地址（不含具体工作区，由 dsh 自己选择）。"""
    return dsh_service.entry()


@router.post("/workspaces/bootstrap")
def bootstrap_workspace(
    payload: WorkspaceBootstrapRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """在 WORKSPACE_ROOT 下创建以目录名命名的工作区，供「AI 创建卡片」使用。"""
    result = dsh_service.bootstrap_workspace(payload.title, payload.directory)
    audit_service.record(
        db,
        action="dsh.workspace.bootstrap",
        target_type="workspace",
        target_id=result["workspace_id"],
        params={
            "path": result["path"],
            "title": result["title"],
            "directory": result.get("directory"),
        },
    )
    return result


@router.post("/workspaces")
def create_workspace(
    payload: WorkspaceCreateRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """把服务器目录注册为 dsh 工作区；同一路径重复调用返回已有工作区。"""
    result = dsh_service.create_workspace(payload.path, payload.title)
    audit_service.record(
        db,
        action="dsh.workspace.create" if result["created"] else "dsh.workspace.reuse",
        target_type="workspace",
        target_id=result["workspace_id"],
        params={"path": result["path"], "title": result["title"]},
    )
    return result
