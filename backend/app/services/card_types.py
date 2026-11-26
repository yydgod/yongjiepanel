"""Card type registry — the frontend renders forms from these specs.

Adding a new managed service kind = register a spec here + implement a collector.
"""

from __future__ import annotations

from typing import Any

CARD_TYPES: list[dict[str, Any]] = [
    {
        "kind": "container",
        "label": "Docker 容器",
        "icon": "box",
        "accent": "teal",
        "description": "监控容器状态、CPU/内存占用、端口映射与运行时长。",
        "target_label": "容器名 / ID",
        "target_placeholder": "例如 nginx-proxy",
        "target_pattern": r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$",
        "tools": [
            "get_status",
            "get_metrics",
            "tail_logs",
            "list_ports",
            "restart_container",
            "stop_container",
            "start_container",
        ],
        "metrics": ["cpu", "memory", "uptime", "ports"],
        "display_defaults": {"showMetrics": True, "showPorts": True, "showUptime": True},
    },
    {
        "kind": "systemd",
        "label": "systemd 服务",
        "icon": "server",
        "accent": "violet",
        "description": "监控 unit 的 active/sub 状态、主进程内存与占用端口。",
        "target_label": "unit 名称",
        "target_placeholder": "例如 nginx.service",
        "target_pattern": r"^[A-Za-z0-9@._:\-]{1,120}$",
        "tools": ["get_status", "get_metrics", "list_ports", "restart_unit"],
        "metrics": ["cpu", "memory", "uptime", "ports"],
        "display_defaults": {"showMetrics": True, "showPorts": True, "showUptime": True},
    },
    {
        "kind": "port",
        "label": "端口服务",
        "icon": "radio",
        "accent": "blue",
        "description": "以监听端口为探针，自动定位所属进程与资源占用。",
        "target_label": "端口",
        "target_placeholder": "例如 8080 或 tcp/5432",
        "target_pattern": r"^(?:(?:tcp|udp)/)?\d{1,5}$",
        "tools": ["get_status", "get_metrics", "list_ports"],
        "metrics": ["cpu", "memory", "uptime"],
        "display_defaults": {"showMetrics": True, "showPorts": True, "showUptime": True},
    },
    {
        "kind": "custom",
        "label": "自定义卡片",
        "icon": "sparkles",
        "accent": "amber",
        "description": "为任意外部服务（SaaS、内网 API）建卡，人工维护状态与说明。",
        "target_label": "目标标识 / URL",
        "target_placeholder": "例如 https://status.example.com",
        "target_pattern": r"^.{1,200}$",
        "tools": ["get_status"],
        "metrics": [],
        "display_defaults": {"showMetrics": False, "showPorts": False, "showUptime": False},
    },
]

_BY_KIND = {spec["kind"]: spec for spec in CARD_TYPES}


def list_card_types() -> list[dict[str, Any]]:
    return CARD_TYPES


def get_card_type(kind: str) -> dict[str, Any] | None:
    return _BY_KIND.get(kind)


def tools_for(kind: str) -> list[str]:
    spec = _BY_KIND.get(kind)
    return list(spec["tools"]) if spec else ["get_status"]


def default_display_config(kind: str) -> dict[str, Any]:
    spec = _BY_KIND.get(kind)
    base = dict(spec["display_defaults"]) if spec else {}
    base.setdefault("showMetrics", True)
    return base
