"""Database bootstrap: create tables + seed demo data on first run."""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import create_all, session_scope
from app.models import Host

log = get_logger("db")


def init_db(seed: bool | None = None) -> None:
    create_all()
    if not (settings.seed_demo if seed is None else seed):
        return
    from app.seeds import seed_database

    with session_scope() as db:
        if db.query(Host).count() == 0:
            seed_database(db)
            log.info("初始化数据库并写入种子数据")
        else:
            log.info("数据库已存在，跳过种子数据")
