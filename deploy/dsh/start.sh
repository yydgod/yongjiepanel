#!/usr/bin/env bash
# 由 systemd 调用：启动 dsh web，并把启动 token 写入面板可读的文件。
set -euo pipefail

DSH_DIR="${DSH_DIR:-/opt/yongjie-dsh}"
DSH_HOME="${DSH_HOME:-/data/yongjie/dsh-home}"
DSH_PORT="${DSH_PORT:-3082}"
DSH_PUBLIC_URL="${DSH_PUBLIC_URL:-}"
TOKEN_FILE="${DSH_TOKEN_FILE:-/data/yongjie/dsh-token}"
LOG_FILE="${DSH_LOG_FILE:-/data/yongjie/dsh.log}"

mkdir -p "$DSH_HOME" /data/yongjie
export DSH_HOME
cd "$DSH_DIR"

args=(web --no-open --host 127.0.0.1 --port "$DSH_PORT")
if [ -n "$DSH_PUBLIC_URL" ]; then
  authority="${DSH_PUBLIC_URL#*://}"
  authority="${authority%%/*}"
  args+=(--public-url "$DSH_PUBLIC_URL" --trusted-host "$authority")
fi

: > "$LOG_FILE"
rm -f "$TOKEN_FILE"
echo "[$(date -Is)] starting dsh on 127.0.0.1:$DSH_PORT" >> "$LOG_FILE"
node apps/cli/lib/bin.js "${args[@]}" >> "$LOG_FILE" 2>&1 &
pid=$!

cleanup() {
  kill -TERM "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}
trap cleanup TERM INT

# dsh 会把带 token 的访问地址打印到日志，这里提取供面板读取。
for _ in $(seq 1 120); do
  token="$(grep -o 'token=[A-Za-z0-9_-]*' "$LOG_FILE" | tail -1 | cut -d= -f2 || true)"
  if [ -n "$token" ]; then
    umask 077
    printf '%s\n' "$token" > "$TOKEN_FILE"
    echo "[$(date -Is)] token written to $TOKEN_FILE" >> "$LOG_FILE"
    break
  fi
  sleep 0.5
done

wait "$pid"
