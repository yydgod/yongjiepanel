"""Database bootstrap: create tables + seed demo data on first run."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import create_all, engine, session_scope
from app.models import Host

log = get_logger("db")


def _ensure_schema() -> None:
    """create_all 不会修改已有表，这里为旧库补充新增列。"""
    inspector = inspect(engine)
    if "service_cards" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("service_cards")}
    if "workspace_path" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE service_cards ADD COLUMN workspace_path VARCHAR(1024)")
        )
    log.info("已为 service_cards 补充 workspace_path 列")


def init_db(seed: bool | None = None) -> None:
    create_all()
    _ensure_schema()
    if not (settings.seed_demo if seed is None else seed):
        return
    from app.seeds import seed_database

    with session_scope() as db:
        if db.query(Host).count() == 0:
            seed_database(db)
            log.info("初始化数据库并写入种子数据")
        else:
            log.info("数据库已存在，跳过种子数据")
