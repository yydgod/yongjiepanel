"""Terminal sessions: independent working directories plus persistent history."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import (
    CONFLICT,
    NOT_CONFIGURED,
    NOT_FOUND,
    UNAVAILABLE,
    VALIDATION,
    AppError,
)

_HISTORY_LOCK = threading.Lock()
_SESSIONS_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class TerminalSession:
    id: str
    title: str
    cwd: Path
    created_at: str
    last_active: str
    previous_cwd: Path | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


_SESSIONS: dict[str, TerminalSession] = {}
_COUNTER = 0


def _ensure_enabled() -> None:
    if not settings.terminal_enabled:
        raise AppError(NOT_CONFIGURED, "终端功能已关闭（TERMINAL_ENABLED=false）", 503)


def _seed_cwd() -> Path:
    home = Path.home()
    return home if home.is_dir() else Path("/")


def _serialize(session: TerminalSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title,
        "cwd": str(session.cwd),
        "created_at": session.created_at,
        "last_active": session.last_active,
    }


def create_session(title: str | None = None) -> dict[str, Any]:
    global _COUNTER
    _ensure_enabled()
    with _SESSIONS_LOCK:
        if len(_SESSIONS) >= settings.terminal_max_sessions:
            raise AppError(
                CONFLICT,
                f"最多同时打开 {settings.terminal_max_sessions} 个终端",
                409,
            )
        _COUNTER += 1
        session = TerminalSession(
            id=uuid.uuid4().hex[:12],
            title=(title or "").strip() or f"终端 {_COUNTER}",
            cwd=_seed_cwd(),
            created_at=_now(),
            last_active=_now(),
        )
        _SESSIONS[session.id] = session
        return _serialize(session)


def list_sessions() -> dict[str, Any]:
    _ensure_enabled()
    with _SESSIONS_LOCK:
        sessions = [_serialize(item) for item in _SESSIONS.values()]
    sessions.sort(key=lambda item: item["created_at"] or "")
    return {"items": sessions}


def close_session(session_id: str) -> None:
    with _SESSIONS_LOCK:
        session = _SESSIONS.pop(session_id, None)
    if session is None:
        raise AppError(NOT_FOUND, f"终端会话不存在: {session_id}", 404)


def _session(session_id: str) -> TerminalSession:
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise AppError(NOT_FOUND, "终端会话不存在或已关闭", 404)
    return session


def history(limit: int = 100) -> dict[str, Any]:
    _ensure_enabled()
    with _HISTORY_LOCK:
        items = _read_history()
    return {"items": items[: max(1, min(limit, settings.terminal_history_limit))]}


def clear_history() -> None:
    with _HISTORY_LOCK:
        _write_history([])


def _history_path() -> Path:
    return Path(settings.terminal_history_file).expanduser()


def _read_history() -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _write_history(items: list[dict[str, Any]]) -> None:
    path = _history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(
            json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        pass


def _record_history(command: str, session: TerminalSession, exit_code: int) -> None:
    entry = {
        "command": command,
        "session_id": session.id,
        "cwd": str(session.cwd),
        "exit_code": exit_code,
        "created_at": _now(),
    }
    with _HISTORY_LOCK:
        items = _read_history()
        items.insert(0, entry)
        _write_history(items[: settings.terminal_history_limit])


def _parse_cd(command: str) -> Path | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts or parts[0] != "cd" or len(parts) > 2:
        return None
    return Path(parts[1]) if len(parts) == 2 else Path("~")


def _result(
    session: TerminalSession, output: str, exit_code: int, started: float, truncated: bool = False
) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "cwd": str(session.cwd),
        "output": output,
        "exit_code": exit_code,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "truncated": truncated,
    }


def _change_directory(session: TerminalSession, raw: Path, started: float) -> dict[str, Any]:
    if str(raw) == "-":
        target = session.previous_cwd
        if target is None:
            return _result(session, "cd: OLDPWD not set\n", 1, started)
    else:
        target = raw.expanduser()
        if not target.is_absolute():
            target = session.cwd / target
        target = target.resolve()
    if not target.exists():
        return _result(session, f"cd: {target}: No such file or directory\n", 1, started)
    if not target.is_dir():
        return _result(session, f"cd: {target}: Not a directory\n", 1, started)
    session.previous_cwd = session.cwd
    session.cwd = target
    return _result(session, "", 0, started)


def exec_command(session_id: str, command: str, timeout: float | None = None) -> dict[str, Any]:
    _ensure_enabled()
    text = command.strip()
    if not text:
        raise AppError(VALIDATION, "命令不能为空", 400)

    session = _session(session_id)
    started = time.monotonic()
    with session.lock:
        session.last_active = _now()

        cd_target = _parse_cd(text)
        if cd_target is not None:
            result = _change_directory(session, cd_target, started)
            session.last_active = _now()
            _record_history(text, session, result["exit_code"])
            return result

        limit = settings.terminal_timeout if timeout is None else min(timeout, 120)
        env = {**os.environ, "TERM": "xterm-256color", "PWD": str(session.cwd)}
        try:
            completed = subprocess.run(
                ["bash", "-lc", text],
                cwd=str(session.cwd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=limit,
                env=env,
                check=False,
            )
            output = completed.stdout.decode("utf-8", errors="replace")
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or b""
            if isinstance(partial, str):
                partial = partial.encode("utf-8", errors="replace")
            output = partial.decode("utf-8", errors="replace")
            output += f"\n[执行超时（{limit:g}s），命令已终止]\n"
            exit_code = 124
        except ValueError as exc:
            raise AppError(VALIDATION, f"命令包含非法字符: {exc}", 400) from exc
        except OSError as exc:
            raise AppError(UNAVAILABLE, f"无法启动命令: {exc}", 500) from exc

        truncated = False
        encoded = output.encode("utf-8")
        if len(encoded) > settings.terminal_max_output_bytes:
            output = encoded[: settings.terminal_max_output_bytes].decode("utf-8", errors="ignore")
            output += "\n…[输出已截断]\n"
            truncated = True

        session.last_active = _now()
        _record_history(text, session, exit_code)
        return _result(session, output, exit_code, started, truncated)
