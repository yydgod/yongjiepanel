#!/usr/bin/env bash
# SQLite 在线备份（不停服），默认保留 14 天
# 用法：
#   bash deploy/backup.sh [数据库路径] [备份目录]
#   RETENTION_DAYS=30 bash deploy/backup.sh
#   PYTHON_BIN=python3.12 bash deploy/backup.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${1:-$ROOT_DIR/backend/data/board.db}"
DEST="${2:-$ROOT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ -n "${PYTHON_BIN:-}" ]; then
  PY="$PYTHON_BIN"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PY="$ROOT_DIR/.venv/bin/python"
else
  PY="python3"
fi

if [ ! -f "$DB" ]; then
  echo "数据库不存在：$DB" >&2
  exit 1
fi

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/board-$STAMP.db"

"$PY" - "$DB" "$OUT" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
    # Python >= 3.7 提供在线备份 API；旧环境退回 VACUUM INTO（SQLite >= 3.27）
    if hasattr(src, "backup"):
        src.backup(dst)
    else:
        safe_target = target.replace("'", "''")
        src.execute(f"VACUUM INTO '{safe_target}'")
PY

chmod 600 "$OUT" 2>/dev/null || true
find "$DEST" -maxdepth 1 -name 'board-*.db' -mtime +"$RETENTION_DAYS" -delete

echo "备份完成：$OUT"
