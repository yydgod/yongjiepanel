"""FastAPI application assembly."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import card_types, cards, dsh, files, host, logs, system, terminal
from app.collectors.scheduler import scheduler
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.init_db import init_db
from app.services.host_monitor import host_monitor

log = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(logging.INFO)
    init_db()
    await scheduler.start()
    await host_monitor.start()
    log.info("看板服务已启动 %s", settings.app_name)
    try:
        yield
    finally:
        await host_monitor.stop()
        await scheduler.stop()


app = FastAPI(
    title="永杰面板 API",
    version=__version__,
    description="永杰面板：服务器总览、应用卡片与 dsh 原生工作区",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def admin_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Optional bearer protection — only active when ADMIN_TOKEN is set."""
    if (
        settings.admin_token
        and request.url.path.startswith(settings.api_prefix)
        and request.method not in ("OPTIONS", "GET")
        and request.headers.get("authorization") != f"Bearer {settings.admin_token}"
    ):
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "denied", "message": "缺少或错误的 ADMIN_TOKEN", "detail": None}},
        )
    return await call_next(request)


for module in (cards, card_types, dsh, files, host, logs, system, terminal):
    app.include_router(module.router, prefix=settings.api_prefix)
