"""dsh（DeepSeek Harness）入口地址与 token 解析。"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from app.core.config import settings


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
