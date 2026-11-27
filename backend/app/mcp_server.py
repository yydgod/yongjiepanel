"""MCP server：让 dsh 中的 AI 直接创建服务、容器与面板卡片。

通过 stdio 由 dsh 的 MCP client 启动，工具内部调用面板 HTTP API：

- 创建工作区（dsh workspace）
- 创建/启动 Docker 容器，并生成卡片
- 创建/启动 systemd 服务，并生成卡片
- 为已有容器、服务、端口或自定义对象创建卡片
- 触发采集并回读卡片状态（CPU、内存、端口、日志可用）

运行方式（dsh profile 配置为 stdio）：
    python -m app.mcp_server
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

PANEL_API = os.environ.get("PANEL_API", "http://127.0.0.1:8000/api").rstrip("/")
UNIT_DIR = Path("/etc/systemd/system")

mcp = FastMCP(
    "yongjie-panel",
    instructions=(
        "永杰面板服务管理工具。创建新卡片时优先使用 create_container 或 "
        "create_systemd_service，它们会一次性完成工作区目录注册、服务启动、卡片创建与指标采集。"
        "如果服务需要自定义代码或镜像，先在 dsh 工作区里编写文件并构建镜像，再调用这些工具运行。"
    ),
)


def _token() -> str:
    token = os.environ.get("PANEL_TOKEN", "").strip()
    if token:
        return token
    candidates = []
    explicit = os.environ.get("PANEL_ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            Path(__file__).resolve().parents[2] / ".env",
            Path(__file__).resolve().parents[1] / ".env",
        ]
    )
    for path in candidates:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("ADMIN_TOKEN="):
                    return stripped.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def _api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    headers = {"Content-Type": "application/json"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{PANEL_API}{path}"
    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.request(method, url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"无法访问面板 API（{url}）：{exc}") from exc
    if response.status_code == 204:
        return {}
    if response.status_code >= 400:
        try:
            error = response.json().get("error") or {}
        except ValueError:
            error = {}
        message = error.get("message") or response.text[:300]
        raise RuntimeError(f"面板 API 失败（{response.status_code}）：{message}")
    return response.json()


def _create_card(
    *,
    title: str,
    card_type: str,
    target_ref: str,
    workspace_path: str | None = None,
    group_name: str = "AI 生成",
    subtitle: str | None = None,
    icon: str | None = None,
    accent: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "card_type": card_type,
        "target_ref": target_ref,
        "group_name": group_name or "AI 生成",
    }
    if workspace_path:
        payload["workspace_path"] = workspace_path
    if subtitle:
        payload["subtitle"] = subtitle
    if icon:
        payload["icon"] = icon
    if accent:
        payload["accent"] = accent
    return _api("POST", "/cards", payload)


def _collect_and_read(card_id: str) -> dict[str, Any]:
    try:
        _api("POST", "/system/collect")
    except RuntimeError:
        pass
    return _api("GET", f"/cards/{card_id}")


def _docker_client():  # type: ignore[no-untyped-def]
    try:
        import docker
    except ImportError as exc:
        raise RuntimeError("缺少 docker Python SDK，请安装 docker 包") from exc
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as exc:  # docker.errors.DockerException 等
        raise RuntimeError(f"无法连接 Docker：{exc}") from exc


def _parse_ports(ports: dict[str, int] | None) -> dict[str, int] | None:
    if not ports:
        return None
    normalized: dict[str, int] = {}
    for key, value in ports.items():
        container_port = str(key)
        if "/" not in container_port:
            container_port += "/tcp"
        normalized[container_port] = int(value)
    return normalized


def _parse_volumes(volumes: list[str] | None) -> dict[str, dict[str, str]] | None:
    if not volumes:
        return None
    parsed: dict[str, dict[str, str]] = {}
    for spec in volumes:
        parts = str(spec).split(":")
        if len(parts) < 2:
            raise RuntimeError(f"卷挂载格式应为 host:container[:mode]：{spec}")
        parsed[parts[0]] = {
            "bind": parts[1],
            "mode": parts[2] if len(parts) > 2 else "rw",
        }
    return parsed


def _host_ports(container: Any) -> list[int]:
    container.reload()
    ports = (container.attrs.get("NetworkSettings") or {}).get("Ports") or {}
    result: set[int] = set()
    for bindings in ports.values():
        for binding in bindings or []:
            host_port = (binding or {}).get("HostPort")
            if host_port:
                result.add(int(host_port))
    return sorted(result)


def _systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@mcp.tool()
def create_workspace(path: str, title: str | None = None) -> dict[str, Any]:
    """把服务器上的目录注册为 dsh 工作区（不会创建目录）。

    path 必须是已存在的目录；返回 workspace_id 与可打开的 dsh URL。
    """
    payload: dict[str, Any] = {"path": path}
    if title:
        payload["title"] = title
    return _api("POST", "/dsh/workspaces", payload)


@mcp.tool()
def create_service_card(
    title: str,
    card_type: str,
    target_ref: str,
    workspace_path: str | None = None,
    group_name: str = "AI 生成",
    subtitle: str | None = None,
    icon: str | None = None,
    accent: str | None = None,
) -> dict[str, Any]:
    """为已有对象创建监控卡片（不创建/启动服务）。

    card_type: container（容器名）、systemd（unit 名，如 foo.service）、port（端口号）、custom。
    workspace_path 可选：填写已存在的目录会同时注册并绑定 dsh 工作区。
    如果是新服务，请优先使用 create_container 或 create_systemd_service。
    """
    card = _create_card(
        title=title,
        card_type=card_type,
        target_ref=target_ref,
        workspace_path=workspace_path,
        group_name=group_name,
        subtitle=subtitle,
        icon=icon,
        accent=accent,
    )
    return _collect_and_read(card["id"])


@mcp.tool()
def create_container(
    name: str,
    image: str,
    title: str | None = None,
    ports: dict[str, int] | None = None,
    env: dict[str, str] | None = None,
    command: str | None = None,
    volumes: list[str] | None = None,
    network: str | None = None,
    restart_policy: str = "unless-stopped",
    workspace_path: str | None = None,
    group_name: str = "AI 生成",
) -> dict[str, Any]:
    """创建并启动 Docker 容器，然后注册工作区、生成卡片并采集指标。

    - name: 容器名；同名容器已存在时复用并确保其处于运行状态
    - image: 镜像名（需已存在；可先用 dsh 终端 docker build）
    - ports: 端口映射，如 {"80/tcp": 8080} 或 {"5432": 15432}
    - env: 环境变量，如 {"MODE": "prod"}
    - volumes: 挂载列表，如 ["/data/app:/app"]
    - workspace_path: 可选，把该目录注册为 dsh 工作区并绑定到卡片
    返回卡片详情（含端口、CPU/内存快照）与容器信息。
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
        raise RuntimeError(f"容器名不合法：{name}")

    client = _docker_client()
    reused = False
    try:
        container = client.containers.get(name)
        reused = True
        if container.status != "running":
            container.start()
    except Exception:
        try:
            container = client.containers.run(
                image,
                command=command or None,
                name=name,
                detach=True,
                ports=_parse_ports(ports),
                environment=env or None,
                volumes=_parse_volumes(volumes),
                network=network or None,
                restart_policy={"Name": restart_policy} if restart_policy else None,
            )
        except Exception as exc:
            raise RuntimeError(f"创建容器失败：{exc}") from exc

    try:
        host_ports = _host_ports(container)
    except Exception:
        host_ports = []

    card = _create_card(
        title=title or name,
        card_type="container",
        target_ref=name,
        workspace_path=workspace_path,
        group_name=group_name,
        subtitle=f"Docker 容器 · {image}",
        icon="box",
        accent="teal",
    )
    detail = _collect_and_read(card["id"])
    return {
        "card": detail,
        "container": {
            "name": name,
            "image": image,
            "id": getattr(container, "short_id", ""),
            "status": getattr(container, "status", "unknown"),
            "reused": reused,
            "host_ports": host_ports,
        },
    }


@mcp.tool()
def create_systemd_service(
    name: str,
    exec_start: str,
    title: str | None = None,
    working_directory: str | None = None,
    description: str | None = None,
    environment: dict[str, str] | None = None,
    user: str | None = None,
    workspace_path: str | None = None,
    group_name: str = "AI 生成",
    overwrite: bool = False,
) -> dict[str, Any]:
    """创建 systemd 服务并启动，然后注册工作区、生成卡片并采集指标。

    - name: 服务名（不含 .service）
    - exec_start: 启动命令，如 "/data/app/run.sh --port 8080"
    - working_directory: 工作目录
    - environment: 环境变量字典
    - user: 运行用户（可选）
    - workspace_path: 可选，把该目录注册为 dsh 工作区并绑定到卡片
    - overwrite: unit 已存在时是否覆盖
    返回卡片详情与服务状态。
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        raise RuntimeError(f"服务名不合法：{name}")
    if not exec_start.strip():
        raise RuntimeError("exec_start 不能为空")

    unit_path = UNIT_DIR / f"{name}.service"
    if unit_path.exists() and not overwrite:
        raise RuntimeError(f"unit 已存在：{unit_path}（如需覆盖请传 overwrite=true）")

    lines = ["[Unit]"]
    lines.append(f"Description={description or title or name}")
    lines.append("After=network-online.target")
    lines.append("Wants=network-online.target")
    lines.append("")
    lines.append("[Service]")
    lines.append("Type=simple")
    if working_directory:
        directory = Path(working_directory).expanduser()
        if not directory.is_dir():
            raise RuntimeError(f"工作目录不存在：{working_directory}")
        lines.append(f"WorkingDirectory={directory}")
    lines.append(f"ExecStart={exec_start}")
    if user:
        lines.append(f"User={user}")
    for key, value in (environment or {}).items():
        escaped = str(value).replace('"', '\\"')
        lines.append(f'Environment="{key}={escaped}"')
    lines.append("Restart=on-failure")
    lines.append("RestartSec=3")
    lines.append("")
    lines.append("[Install]")
    lines.append("WantedBy=multi-user.target")
    lines.append("")

    try:
        unit_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"写入 unit 失败：{exc}") from exc

    reload_result = _systemctl("daemon-reload")
    if reload_result.returncode != 0:
        raise RuntimeError(f"systemctl daemon-reload 失败：{reload_result.stderr.strip()}")
    start_result = _systemctl("enable", "--now", f"{name}.service")
    if start_result.returncode != 0:
        raise RuntimeError(f"启动服务失败：{start_result.stderr.strip()}")

    active = _systemctl("is-active", f"{name}.service")
    card = _create_card(
        title=title or name,
        card_type="systemd",
        target_ref=f"{name}.service",
        workspace_path=workspace_path,
        group_name=group_name,
        subtitle=description or f"systemd 服务 · {name}.service",
        icon="server",
        accent="violet",
    )
    detail = _collect_and_read(card["id"])
    return {
        "card": detail,
        "service": {
            "unit": f"{name}.service",
            "active": active.stdout.strip() == "active",
            "state": active.stdout.strip() or active.stderr.strip(),
            "unit_path": str(unit_path),
        },
    }


@mcp.tool()
def list_cards(query: str | None = None) -> dict[str, Any]:
    """列出面板上的卡片（可按名称、容器、端口搜索）。"""
    suffix = f"?q={quote(query, safe='')}" if query else ""
    return _api("GET", f"/cards{suffix}")


@mcp.tool()
def get_card(card_id: str) -> dict[str, Any]:
    """读取一张卡片的详情、状态、端口与工作区目录。"""
    return _api("GET", f"/cards/{card_id}")


@mcp.tool()
def collect_now() -> dict[str, Any]:
    """立即执行一轮采集，刷新所有卡片的 CPU/内存/端口等信息。"""
    return _api("POST", "/system/collect")


if __name__ == "__main__":
    mcp.run()
