"""Sandboxed server-side file browser.

All paths are resolved against ``settings.file_root`` (default ``/``) and any
attempt to escape that root is rejected with a ``denied`` error.
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import stat as stat_lib
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import CONFLICT, DENIED, INTERNAL, NOT_FOUND, VALIDATION, AppError

MAX_DIR_ENTRIES = 2000

# 搜索时任意层级跳过的缓存/依赖目录
SEARCH_SKIP_ANYWHERE = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
# 根目录为 / 时跳过的伪文件系统
SEARCH_SKIP_AT_ROOT = {"proc", "sys", "dev", "run", "snap"}


def root() -> Path:
    return Path(settings.file_root).expanduser().resolve()


def resolve(path: str | None) -> Path:
    """把前端路径（形如 ``/etc``）解释为沙箱根目录下的相对路径。"""
    raw = (path or "/").strip() or "/"
    if "\x00" in raw:
        raise AppError(VALIDATION, "路径包含非法字符", 400)
    base = root()
    target = (base / raw.lstrip("/")).resolve()
    if target != base and base not in target.parents:
        raise AppError(DENIED, "路径超出允许访问的根目录", 403)
    return target


def relative(path: Path) -> str:
    base = root()
    if path == base:
        return "/"
    return "/" + path.relative_to(base).as_posix()


def _modified_at(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except OSError:
        return None


def _guard(exc: OSError, message: str) -> AppError:
    if isinstance(exc, PermissionError):
        return AppError(DENIED, message, 403)
    return AppError(INTERNAL, f"{message}: {exc.strerror or exc}", 500)


def _entry(path: Path, entry: os.DirEntry[str]) -> dict[str, Any]:
    try:
        info = entry.stat(follow_symlinks=False)
    except OSError:
        info = None
    # 跟随符号链接判断目录，便于展开；越界访问仍会被 resolve() 拦截
    is_dir = entry.is_dir(follow_symlinks=True)
    return {
        "name": entry.name,
        "path": relative(path / entry.name),
        "is_dir": is_dir,
        "is_symlink": entry.is_symlink(),
        "size": None if is_dir or info is None else info.st_size,
        "mode": stat_lib.filemode(info.st_mode) if info else "",
        "modified_at": (
            datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec="seconds")
            if info
            else None
        ),
        "hidden": entry.name.startswith("."),
    }


def list_dir(path: str | None) -> dict[str, Any]:
    target = resolve(path)
    if not target.exists():
        raise AppError(NOT_FOUND, f"路径不存在: {relative(target)}", 404)
    if not target.is_dir():
        raise AppError(VALIDATION, "目标不是目录", 400)

    items: list[dict[str, Any]] = []
    try:
        with os.scandir(target) as entries:
            for entry in entries:
                items.append(_entry(target, entry))
    except PermissionError as exc:
        raise _guard(exc, "没有权限读取该目录") from exc

    items.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))
    truncated = len(items) > MAX_DIR_ENTRIES
    return {
        "root": relative(root()),
        "absolute_root": str(root()),
        "path": relative(target),
        "parent": relative(target.parent) if target != root() else None,
        "items": items[:MAX_DIR_ENTRIES],
        "truncated": truncated,
    }


def read_file(path: str) -> dict[str, Any]:
    target = resolve(path)
    if not target.exists():
        raise AppError(NOT_FOUND, f"文件不存在: {relative(target)}", 404)
    if not target.is_file():
        raise AppError(VALIDATION, "目标不是常规文件", 400)

    preview_limit = settings.file_preview_bytes
    try:
        size = target.stat().st_size
        with target.open("rb") as handle:
            data = handle.read(preview_limit + 1)
    except OSError as exc:
        raise _guard(exc, "读取文件失败") from exc

    truncated = len(data) > preview_limit
    data = data[:preview_limit]
    binary = b"\x00" in data
    content = "" if binary else data.decode("utf-8", errors="replace")
    return {
        "path": relative(target),
        "name": target.name,
        "size": size,
        "content": content,
        "binary": binary,
        "truncated": truncated,
        "editable": not binary and not truncated and size <= settings.file_max_bytes,
        "mime": mimetypes.guess_type(target.name)[0] or "text/plain",
        "modified_at": _modified_at(target),
    }


def write_file(path: str, content: str) -> dict[str, Any]:
    target = resolve(path)
    if target.exists() and target.is_dir():
        raise AppError(VALIDATION, "目标是目录，无法写入", 400)
    if not target.parent.exists():
        raise AppError(NOT_FOUND, f"父目录不存在: {relative(target.parent)}", 404)

    data = content.encode("utf-8")
    if len(data) > settings.file_max_bytes:
        raise AppError(
            VALIDATION,
            f"文件内容超出上限（{settings.file_max_bytes} 字节）",
            413,
        )
    try:
        target.write_bytes(data)
    except OSError as exc:
        raise _guard(exc, "写入文件失败") from exc
    return {
        "path": relative(target),
        "size": len(data),
        "modified_at": _modified_at(target),
    }


def make_dir(path: str) -> dict[str, Any]:
    target = resolve(path)
    if target.exists():
        raise AppError(CONFLICT, f"路径已存在: {relative(target)}", 409)
    if not target.parent.exists():
        raise AppError(NOT_FOUND, f"父目录不存在: {relative(target.parent)}", 404)
    try:
        target.mkdir()
    except OSError as exc:
        raise _guard(exc, "创建目录失败") from exc
    return {"path": relative(target), "is_dir": True}


def rename(path: str, target_path: str) -> dict[str, Any]:
    source = resolve(path)
    destination = resolve(target_path)
    if source == root():
        raise AppError(DENIED, "不能重命名根目录", 403)
    if not source.exists():
        raise AppError(NOT_FOUND, f"路径不存在: {relative(source)}", 404)
    if destination.exists():
        raise AppError(CONFLICT, f"目标已存在: {relative(destination)}", 409)
    if not destination.parent.exists():
        raise AppError(NOT_FOUND, f"目标目录不存在: {relative(destination.parent)}", 404)
    if source.is_dir() and source in destination.parents:
        raise AppError(VALIDATION, "不能把目录移动到自身的子目录中", 400)
    try:
        source.rename(destination)
    except OSError as exc:
        raise _guard(exc, "重命名失败") from exc
    return {"path": relative(destination), "from": relative(source)}


def delete(path: str, recursive: bool = False) -> dict[str, Any]:
    target = resolve(path)
    if target == root():
        raise AppError(DENIED, "不能删除根目录", 403)
    if not target.exists():
        raise AppError(NOT_FOUND, f"路径不存在: {relative(target)}", 404)

    target_path = relative(target)
    try:
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif recursive:
            shutil.rmtree(target)
        else:
            target.rmdir()
    except FileNotFoundError as exc:
        raise AppError(NOT_FOUND, f"路径不存在: {target_path}", 404) from exc
    except PermissionError as exc:
        raise _guard(exc, "删除失败，权限不足") from exc
    except OSError as exc:
        raise AppError(CONFLICT, "目录非空，请确认后递归删除", 409) from exc
    return {"path": target_path, "deleted": True}


def search(query: str, limit: int = 50) -> dict[str, Any]:
    """按名称广度优先搜索文件/目录，优先覆盖浅层路径，受超时与扫描条目数约束。"""
    needle = query.strip().lower()
    if not needle:
        return {"query": query, "items": [], "truncated": False, "scanned": 0}

    base = root()
    deadline = time.monotonic() + settings.file_search_timeout
    max_scan = settings.file_search_max_scan
    results: list[dict[str, Any]] = []
    scanned = 0
    truncated = False
    queue: deque[Path] = deque([base])

    while queue:
        current = queue.popleft()
        if time.monotonic() > deadline or scanned >= max_scan:
            truncated = True
            break
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue

        at_root = current == base
        for entry in entries:
            scanned += 1
            if scanned >= max_scan or time.monotonic() > deadline:
                truncated = True
                break
            name = entry.name
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if is_dir:
                if name in SEARCH_SKIP_ANYWHERE or (at_root and name in SEARCH_SKIP_AT_ROOT):
                    continue
                queue.append(Path(entry.path))
            if needle not in name.lower():
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                info = None
            results.append(
                {
                    "name": name,
                    "path": relative(current / name),
                    "is_dir": is_dir,
                    "is_symlink": entry.is_symlink(),
                    "size": None if is_dir or info is None else info.st_size,
                    "mode": stat_lib.filemode(info.st_mode) if info else "",
                    "modified_at": (
                        datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec="seconds")
                        if info
                        else None
                    ),
                    "hidden": name.startswith("."),
                }
            )
            if len(results) >= limit:
                truncated = True
                break
        if truncated:
            break

    results.sort(
        key=lambda item: (
            0 if item["name"].lower() == needle else 1 if item["name"].lower().startswith(needle) else 2,
            not item["is_dir"],
            item["name"].lower(),
        )
    )
    return {
        "query": query,
        "items": results[:limit],
        "truncated": truncated,
        "scanned": scanned,
    }
