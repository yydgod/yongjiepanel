"""Unified error model: every failure is a classified AppError."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# error codes shared with the frontend
NOT_FOUND = "not_found"
VALIDATION = "validation"
CONFLICT = "conflict"
NOT_CONFIGURED = "not_configured"
UNAVAILABLE = "unavailable"
DENIED = "denied"
TIMEOUT = "timeout"
UPSTREAM = "upstream_error"
INTERNAL = "internal_error"


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "detail": self.detail}}


def not_found(what: str, ident: str) -> AppError:
    return AppError(NOT_FOUND, f"{what} 不存在: {ident}", 404)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": VALIDATION,
                    "message": "请求参数校验失败",
                    "detail": [
                        {"loc": list(err.get("loc", [])), "msg": err.get("msg", "")}
                        for err in exc.errors()
                    ],
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail), "detail": None}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": INTERNAL,
                    "message": "服务内部错误",
                    "detail": type(exc).__name__,
                }
            },
        )
