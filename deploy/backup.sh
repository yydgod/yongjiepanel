#!/usr/bin/env bash
# SQLite 在线备份（不停服），默认保留 14 天
# 用法：
#   bash deploy/backup.sh [数据库路径] [备份目录]
#   RETENTION_DAYS=30 bash deploy/backup.sh
set -euo pipefail

DB="${1:-backend/data/board.db}"
DEST="${2:-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ ! -f "$DB" ]; then
  echo "数据库不存在：$DB" >&2
  exit 1
fi

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/board-$STAMP.db"

python3 - "$DB" "$OUT" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
PY

chmod 600 "$OUT" 2>/dev/null || true
find "$DEST" -maxdepth 1 -name 'board-*.db' -mtime +"$RETENTION_DAYS" -delete

echo "备份完成：$OUT"
