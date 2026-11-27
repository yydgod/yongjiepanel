"""Seed data: local host and cards detected on this machine."""

from __future__ import annotations

import subprocess

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Host
from app.schemas.card import CardCreate
from app.services import card_service

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


def _seed_cards(db: Session) -> None:
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
        ),
    )


def seed_database(db: Session) -> None:
    host = Host(name="本机", kind="local", status="online")
    db.add(host)
    db.flush()
    db.commit()
    _seed_cards(db)
    log.info("种子数据写入完成: host=%s", host.id)
