"""Seed data: local host, provider presets, and cards detected on this machine."""

from __future__ import annotations

import subprocess

from sqlalchemy.orm import Session

from app.ai.providers import PRESETS
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import encrypt_secret
from app.models import Host, Provider
from app.schemas.card import AgentConfigIn, CardCreate
from app.services import card_service
from app.services.card_types import tools_for

log = get_logger("seeds")

_SKIP_UNITS = ("systemd-", "dbus", "getty", "user@", "polkit", "chronyd", "auditd", "rsyslog")


def _docker_names(limit: int = 3) -> list[str]:
    try:
        import docker

        client = docker.from_env(timeout=3)
        names = [container.name for container in client.containers.list()]
        return [name for name in names if not name.startswith("yongjie-panel")][:limit]
    except Exception as exc:  # noqa: BLE001
        log.info("跳过容器种子（Docker 不可用）: %s", exc)
        return []


def _systemd_units(limit: int = 1) -> list[str]:
    try:
        proc = subprocess.run(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-legend",
                "--no-pager",
                "--plain",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        log.info("跳过 systemd 种子: %s", exc)
        return []
    units: list[str] = []
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if not parts or not parts[0].endswith(".service"):
            continue
        if any(token in parts[0] for token in _SKIP_UNITS):
            continue
        units.append(parts[0])
    return units[:limit]


def seed_providers(db: Session) -> list[Provider]:
    keys = {
        "deepseek": settings.deepseek_api_key,
        "hunyuan": settings.hunyuan_api_key,
        "qwen": settings.qwen_api_key,
    }
    created: list[Provider] = []
    for index, (kind, key) in enumerate(keys.items()):
        preset = PRESETS[kind]
        provider = Provider(
            name=preset["label"],
            kind=kind,
            base_url=preset["base_url"],
            default_model=preset["models"][0],
            models=list(preset["models"]),
            api_key_encrypted=encrypt_secret(key) if key else None,
            extra=preset.get("extra", {}),
            is_default=(index == 0),
            enabled=True,
        )
        db.add(provider)
        created.append(provider)
    db.flush()
    return created


def _agent_prompt(title: str, kind: str, target: str) -> str:
    return (
        f"你是「{title}」的专属运维 agent（类型 {kind}，目标 {target}）。\n"
        "职责：先读取状态与日志确认事实，再给出诊断与处置建议；"
        "遇到重启、停止等破坏性操作必须说明影响并等待用户确认；回答简洁、使用中文。"
    )


def _seed_cards(db: Session, providers: list[Provider]) -> None:
    provider_id = providers[0].id if providers else None
    order = 0

    for name in _docker_names():
        order += 10
        card_service.create_card(
            db,
            CardCreate(
                title=name,
                subtitle="本机 Docker 容器 · 自动发现",
                card_type="container",
                target_ref=name,
                group_name="容器应用",
                icon="box",
                accent="teal",
                sort_order=order,
                agent=AgentConfigIn(
                    name=f"{name} 助手",
                    provider_id=provider_id,
                    tools=tools_for("container"),
                    system_prompt=_agent_prompt(name, "container", name),
                ),
            ),
        )

    order += 10
    card_service.create_card(
        db,
        CardCreate(
            title="永杰面板 API",
            subtitle="FastAPI 服务 · 端口 8000",
            card_type="port",
            target_ref="8000",
            group_name="自建服务",
            icon="radio",
            accent="blue",
            sort_order=order,
            agent=AgentConfigIn(
                name="API 守护者",
                provider_id=provider_id,
                tools=tools_for("port"),
                system_prompt=_agent_prompt("永杰面板 API", "port", "8000"),
            ),
        ),
    )

    for unit in _systemd_units():
        order += 10
        card_service.create_card(
            db,
            CardCreate(
                title=unit.replace(".service", ""),
                subtitle="systemd 服务单元",
                card_type="systemd",
                target_ref=unit,
                group_name="系统服务",
                icon="server",
                accent="violet",
                sort_order=order,
                agent=AgentConfigIn(
                    name="unit 助手",
                    provider_id=provider_id,
                    tools=tools_for("systemd"),
                    system_prompt=_agent_prompt(unit, "systemd", unit),
                ),
            ),
        )

    order += 10
    card_service.create_card(
        db,
        CardCreate(
            title="对象存储网关",
            subtitle="自定义卡片示例 · 人工维护状态",
            card_type="custom",
            target_ref="https://status.example.com",
            group_name="外部依赖",
            icon="globe",
            accent="amber",
            sort_order=order,
            enabled=True,
            agent=AgentConfigIn(
                name="外部依赖助手",
                provider_id=provider_id,
                tools=tools_for("custom"),
                system_prompt=_agent_prompt("对象存储网关", "custom", "外部 API"),
            ),
        ),
    )


def seed_database(db: Session) -> None:
    host = Host(name="本机", kind="local", status="online")
    db.add(host)
    db.flush()
    providers = seed_providers(db)
    db.commit()
    _seed_cards(db, providers)
    log.info("种子数据写入完成: host=%s providers=%s", host.id, len(providers))
