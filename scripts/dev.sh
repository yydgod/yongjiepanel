#!/usr/bin/env bash
# 并行启动 FastAPI 与 Vite，Ctrl+C 一起退出。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "[dev] 未找到 .venv，请先执行 make install" >&2
  exit 1
fi

cleanup() {
  echo ""
  echo "[dev] 正在停止服务…"
  kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev] 启动后端 http://127.0.0.1:8000"
(cd backend && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
API_PID=$!

echo "[dev] 启动前端 http://127.0.0.1:5173"
(cd frontend && npm run dev) &
WEB_PID=$!

wait
