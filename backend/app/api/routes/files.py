"""File manager endpoints: browse, read, save, create, rename and delete."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.file import FileMkdirRequest, FileRenameRequest, FileWriteRequest
from app.services import audit_service, file_service

router = APIRouter(prefix="/files", tags=["files"])


def _target(path: str) -> str:
    """audit_logs.target_id 仅 48 字符，保留尾部便于识别。"""
    return path if len(path) <= 48 else f"…{path[-47:]}"


@router.get("/list")
def list_files(path: str = Query(default="/", max_length=4096)) -> dict[str, Any]:
    return file_service.list_dir(path)


@router.get("/search")
def search_files(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return file_service.search(q, limit=limit)


@router.get("/read")
def read_file(path: str = Query(min_length=1, max_length=4096)) -> dict[str, Any]:
    return file_service.read_file(path)


@router.put("/write")
def write_file(payload: FileWriteRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    result = file_service.write_file(payload.path, payload.content)
    audit_service.record(
        db,
        action="file.write",
        target_type="file",
        target_id=_target(result["path"]),
        params={"path": result["path"], "size": result["size"]},
    )
    return result


@router.post("/mkdir", status_code=201)
def make_dir(payload: FileMkdirRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    result = file_service.make_dir(payload.path)
    audit_service.record(
        db,
        action="file.mkdir",
        target_type="file",
        target_id=_target(result["path"]),
        params={"path": result["path"]},
    )
    return result


@router.post("/rename")
def rename(
    payload: FileRenameRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    result = file_service.rename(payload.path, payload.target)
    audit_service.record(
        db,
        action="file.rename",
        target_type="file",
        target_id=_target(result["from"]),
        params={"path": result["from"], "target": result["path"]},
    )
    return result


@router.delete("")
def delete_path(
    path: str = Query(min_length=1, max_length=4096),
    recursive: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = file_service.delete(path, recursive=recursive)
    audit_service.record(
        db,
        action="file.delete",
        target_type="file",
        target_id=_target(result["path"]),
        params={"path": result["path"], "recursive": recursive},
    )
    return result
