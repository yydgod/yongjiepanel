"""dsh（DeepSeek Harness）入口地址、token 与工作区注册。"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.errors import INTERNAL, NOT_CONFIGURED, NOT_FOUND, UPSTREAM, VALIDATION, AppError
from app.services import file_service

_STORE_LOCK = threading.Lock()


def token() -> str:
    """优先读取 start.sh 写入的 token 文件，支持 dsh 重启后轮换。"""
    path = Path(settings.dsh_token_file).expanduser()
    try:
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    return settings.dsh_token


def configured() -> bool:
    return bool(settings.dsh_base_url and token())


def public_base() -> str:
    """浏览器可访问的 dsh 地址；生产环境通常是独立的 dsh 子域名。"""
    return (settings.dsh_public_url or settings.dsh_base_url).rstrip("/")


def url(workspace_id: str | None = None) -> str:
    params = []
    if workspace_id:
        params.append(f"workspace={quote(workspace_id)}")
    params.append(f"token={quote(token())}")
    return f"{public_base()}/?{'&'.join(params)}"


def entry() -> dict[str, object]:
    if not configured():
        return {"configured": False, "reason": "未配置 dsh 地址或 token"}
    return {"configured": True, "url": url()}


def _remote_rpc(endpoint: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """调用运行中 dsh 的 Remote API；dsh 未运行（连接失败）时返回 None。"""
    if not settings.dsh_remote_write or not configured():
        return None
    base = settings.dsh_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            # 用 token 换取 Web 会话 cookie，随后 RPC 依赖该 cookie
            client.get(f"{base}/", params={"token": token()})
            response = client.post(
                f"{base}/api/{endpoint}",
                json={
                    "type": "client-request",
                    "rpcId": f"panel-{uuid.uuid4().hex}",
                    "method": endpoint,
                    "payload": {"args": {"request": args}},
                },
            )
            response.raise_for_status()
            body = response.json()
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout):
        return None
    except httpx.HTTPStatusError as exc:
        raise AppError(UPSTREAM, f"dsh 接口 {endpoint} 返回 {exc.response.status_code}", 502) from exc
    except httpx.HTTPError as exc:
        raise AppError(UPSTREAM, f"调用 dsh 接口 {endpoint} 失败: {exc}", 502) from exc
    except ValueError as exc:
        raise AppError(UPSTREAM, f"dsh 接口 {endpoint} 返回非 JSON 响应", 502) from exc

    result = body.get("result") if isinstance(body, dict) else None
    if not isinstance(result, dict) or result.get("ok") is not True:
        error = result.get("error") if isinstance(result, dict) else None
        message = (error or {}).get("message") or "未知错误"
        code = (error or {}).get("code") or "unknown"
        raise AppError(UPSTREAM, f"dsh 拒绝 {endpoint}: {code} · {message}", 502)
    value = result.get("value")
    return value if isinstance(value, dict) else {}


def _remote_title(
    workspace_id: str, workspace: dict[str, Any], title: str | None
) -> dict[str, Any]:
    desired = (title or "").strip()
    if not desired or not workspace_id or workspace.get("title") == desired:
        return workspace
    try:
        renamed = _remote_rpc("workspace/rename", {"workspaceId": workspace_id, "title": desired})
    except AppError:
        return workspace
    if isinstance(renamed, dict) and isinstance(renamed.get("workspace"), dict):
        return renamed["workspace"]
    return workspace


def workspace_store() -> Path:
    """dsh 工作区注册表与 yongjie-cards.json 位于同一 storages 目录。"""
    return Path(settings.dsh_cards_store).expanduser().with_name("workspace.json")


def cards_store() -> Path:
    return Path(settings.dsh_cards_store).expanduser()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _load_store(store: Path) -> dict[str, Any]:
    if not store.exists():
        raise AppError(
            NOT_CONFIGURED,
            "未找到 dsh 工作区注册表，请先完成 dsh 部署",
            503,
        )
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(UPSTREAM, "dsh 工作区注册表无法解析", 500) from exc
    if not isinstance(data, dict):
        raise AppError(UPSTREAM, "dsh 工作区注册表格式不正确", 500)
    return data


def _load_cards_store(store: Path) -> dict[str, Any]:
    if not store.exists():
        return {"unit": {"name": "yongjie-cards", "version": 1}, "cards": []}
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(UPSTREAM, "yongjie-cards.json 无法解析", 500) from exc
    if not isinstance(data, dict):
        raise AppError(UPSTREAM, "yongjie-cards.json 格式不正确", 500)
    return data


def _store_sections(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    tables = data.setdefault("tables", {})
    if not isinstance(tables, dict):
        tables = {}
        data["tables"] = tables
    table = tables.setdefault("workspaces", {})
    if not isinstance(table, dict):
        table = {}
        tables["workspaces"] = table
    global_section = data.setdefault("global", {})
    if not isinstance(global_section, dict):
        global_section = {}
        data["global"] = global_section
    ids = global_section.setdefault("workspaceIds", [])
    if not isinstance(ids, list):
        ids = []
        global_section["workspaceIds"] = ids
    return table, ids


def _register_workspace(data: dict[str, Any], target: Path, title: str | None) -> tuple[str, bool]:
    table, ids = _store_sections(data)
    existing = next(
        (wid for wid, item in table.items() if isinstance(item, dict) and item.get("path") == str(target)),
        None,
    )
    created = existing is None
    workspace_id = existing or str(uuid.uuid4())
    if created:
        now = _now()
        table[workspace_id] = {
            "path": str(target),
            "title": (title or "").strip() or target.name or str(target),
            "sessionIds": [],
            "createdAt": now,
            "updatedAt": now,
        }
        ids.append(workspace_id)
    return workspace_id, created


def _workspace_result(workspace_id: str, entry: dict[str, Any], created: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "workspace_id": workspace_id,
        "path": entry.get("path"),
        "title": entry.get("title"),
        "created": created,
    }
    if configured():
        result.update(configured=True, url=url(workspace_id))
    else:
        result.update(configured=False, reason="未配置 dsh 地址或 token")
    return result


def _workspace_at(target: Path, title: str | None) -> dict[str, Any]:
    """在已存在的目录上注册 dsh 工作区（运行中优先走 dsh API）。"""
    remote = _remote_rpc("workspace/create", {"path": str(target)})
    if remote is not None:
        workspace = remote.get("workspace") or {}
        workspace_id = str(workspace.get("workspaceId") or "")
        workspace = _remote_title(workspace_id, workspace, title)
        result: dict[str, Any] = {
            "workspace_id": workspace_id,
            "path": workspace.get("path") or str(target),
            "title": workspace.get("title"),
            "created": bool(remote.get("created")),
        }
        result.update(configured=True, url=url(workspace_id))
        return result

    store = workspace_store()
    with _STORE_LOCK:
        data = _load_store(store)
        workspace_id, created = _register_workspace(data, target, title)
        if created:
            _persist(store, data)

    table = data["tables"]["workspaces"]
    return _workspace_result(workspace_id, table.get(workspace_id) or {}, created)


def create_workspace(path: str, title: str | None = None) -> dict[str, Any]:
    """把服务器上的目录注册为 dsh 工作区（运行中优先走 dsh API）。"""
    target = file_service.resolve(path)
    if not target.exists():
        raise AppError(NOT_FOUND, f"目录不存在: {file_service.relative(target)}", 404)
    if not target.is_dir():
        raise AppError(VALIDATION, "只能选择目录创建 dsh 工作区", 400)
    return _workspace_at(target, title)


def bootstrap_workspace(title: str | None, directory: str | None = None) -> dict[str, Any]:
    """在配置的工作区根目录下创建目录，并注册同名 dsh 工作区。

    供「AI 创建卡片」弹窗使用：目录名即卡片/工作区名称，创建后可直接在 dsh 中打开。
    """
    root = Path(settings.workspace_root).expanduser()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(INTERNAL, f"无法创建工作区根目录 {root}: {exc}", 500) from exc

    name = (directory or "").strip() or f"card-{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
        raise AppError(
            VALIDATION,
            "目录名称只能包含字母、数字、点、下划线和连字符，且不能以符号开头",
            400,
        )

    root_resolved = root.resolve()
    target = (root_resolved / name).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise AppError(VALIDATION, "目录名称不合法", 400)
    if target.exists() and not target.is_dir():
        raise AppError(VALIDATION, "同名文件已存在，无法创建目录", 400)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(INTERNAL, f"创建目录失败: {exc}", 500) from exc

    clean_title = (title or "").strip() or name
    result = _workspace_at(target, clean_title)
    result.update(directory=name, absolute_path=str(target))
    return result


def bind_card(card: dict[str, Any], path: str) -> dict[str, Any]:
    """把卡片绑定到目录：注册工作区并更新 yongjie-cards.json。"""
    target = file_service.resolve(path)
    if not target.exists():
        raise AppError(NOT_FOUND, f"工作区目录不存在: {file_service.relative(target)}", 404)
    if not target.is_dir():
        raise AppError(VALIDATION, "工作区目录必须是目录", 400)

    desired_title = card.get("title") or target.name
    cards_path = cards_store()

    remote = _remote_rpc("workspace/create", {"path": str(target)})
    if remote is not None:
        workspace = remote.get("workspace") or {}
        workspace_id = str(workspace.get("workspaceId") or "")
        workspace = _remote_title(workspace_id, workspace, desired_title)
        entry = {
            "path": workspace.get("path") or str(target),
            "title": workspace.get("title") or desired_title,
        }
        with _STORE_LOCK:
            _write_card_mapping(cards_path, card, target, workspace_id, entry["title"])
        result = _workspace_result(workspace_id, entry, bool(remote.get("created")))
        result.update(bound=True, card_id=card.get("id"))
        return result

    store = workspace_store()
    if not store.exists():
        return {
            "bound": False,
            "path": str(target),
            "reason": "未找到 dsh 工作区注册表，目录已保存但暂未注册",
        }

    with _STORE_LOCK:
        data = _load_store(store)
        workspace_id, created = _register_workspace(data, target, card.get("title"))
        if created:
            _persist(store, data)

        table = data["tables"]["workspaces"]
        entry = table.get(workspace_id) or {}
        if not created and entry.get("title") != desired_title:
            entry["title"] = desired_title
            entry["updatedAt"] = _now()
            _persist(store, data)

        _write_card_mapping(cards_path, card, target, workspace_id, desired_title)

    result = _workspace_result(workspace_id, entry, created)
    result.update(bound=True, card_id=card.get("id"))
    return result


def _write_card_mapping(
    store: Path, card: dict[str, Any], target: Path, workspace_id: str, title: str
) -> None:
    payload = {
        "card_id": card.get("id"),
        "workspace_id": workspace_id,
        "path": str(target),
        "title": title,
        "icon": card.get("icon"),
        "accent": card.get("accent"),
        "group": card.get("group_name"),
        "card_type": card.get("card_type"),
        "target_ref": card.get("target_ref"),
    }
    data = _load_cards_store(store)
    items = data.setdefault("cards", [])
    if not isinstance(items, list):
        items = []
        data["cards"] = items
    current = next(
        (
            item
            for item in items
            if isinstance(item, dict) and item.get("card_id") == card.get("id")
        ),
        None,
    )
    if current is None:
        items.append(payload)
    else:
        current.update(payload)
    _persist(store, data)


def unbind_card(card_id: str) -> dict[str, Any]:
    """移除卡片的工作区映射，不改动 workspace.json 中的工作区本身。"""
    store = cards_store()
    if not store.exists():
        return {"unbound": False}
    with _STORE_LOCK:
        data = _load_cards_store(store)
        items = data.get("cards")
        if not isinstance(items, list):
            return {"unbound": False}
        remaining = [
            item
            for item in items
            if not (isinstance(item, dict) and item.get("card_id") == card_id)
        ]
        if len(remaining) == len(items):
            return {"unbound": False}
        data["cards"] = remaining
        _persist(store, data)
    return {"unbound": True}


def lookup_workspace(path: str | None) -> dict[str, Any] | None:
    """按目录查找已注册的工作区（用于卡片映射缺失时自愈）。"""
    if not path:
        return None
    try:
        target = file_service.resolve(path)
    except AppError:
        return None
    store = workspace_store()
    if not store.exists():
        return None
    try:
        data = _load_store(store)
    except AppError:
        return None
    table = data.get("tables", {}).get("workspaces", {})
    for workspace_id, item in table.items():
        if isinstance(item, dict) and item.get("path") == str(target):
            return {
                "workspace_id": workspace_id,
                "path": item.get("path"),
                "title": item.get("title"),
            }
    return None


def _persist(store: Path, data: dict[str, Any]) -> None:
    backup = store.with_name(
        f"{store.name}.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    )
    tmp = store.with_name(f".{store.name}.tmp")
    try:
        if store.exists():
            shutil.copy2(store, backup)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, store)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise AppError(INTERNAL, f"写入 dsh 注册表失败: {exc.strerror or exc}", 500) from exc
