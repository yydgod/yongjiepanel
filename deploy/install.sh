#!/usr/bin/env bash
# 永杰面板一键安装（项目目录内操作，不使用 sudo）
# 用法：
#   bash deploy/install.sh [项目目录]
#   PYTHON_BIN=python3.12 bash deploy/install.sh /opt/yongjie-panel
#   SKIP_FRONTEND=1 bash deploy/install.sh        # 只装后端
set -euo pipefail

APP_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_FRONTEND="${SKIP_FRONTEND:-0}"

cd "$APP_DIR"

echo "==> 项目目录：$APP_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "未找到 $PYTHON_BIN，请先安装 Python 3.11+（可通过 PYTHON_BIN 指定解释器）" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python 版本过低：$("$PYTHON_BIN" -V 2>&1)，需要 >= 3.11" >&2
  exit 1
fi

if [ "$SKIP_FRONTEND" != "1" ]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "未找到 node，请安装 Node.js 20+（或使用 SKIP_FRONTEND=1 仅部署后端）" >&2
    exit 1
  fi
  NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
  if [ "$NODE_MAJOR" -lt 20 ]; then
    echo "Node 版本过低：$(node -v)，需要 >= 20" >&2
    exit 1
  fi
fi

echo "==> 创建虚拟环境"
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt

if [ "$SKIP_FRONTEND" != "1" ]; then
  echo "==> 构建前端"
  cd frontend
  npm ci || npm install
  npm run build
  cd ..
  echo "==> 前端产物：$APP_DIR/frontend/dist（复制到 nginx 根目录后生效）"
fi

echo "==> 准备 .env"
if [ ! -f .env ]; then
  "$PYTHON_BIN" - <<'PY'
import pathlib, secrets
src = pathlib.Path('.env.example').read_text(encoding='utf-8')
src = src.replace(
    'SECRET_KEY=change-me-to-a-random-32byte-secret',
    f'SECRET_KEY={secrets.token_urlsafe(32)}',
)
pathlib.Path('.env').write_text(src, encoding='utf-8')
print('已根据 .env.example 生成 .env，并写入随机 SECRET_KEY')
PY
  chmod 600 .env
else
  echo ".env 已存在，跳过（如需覆盖请先备份并删除）"
fi

echo "==> 初始化数据库"
(cd backend && ../.venv/bin/python -c "from app.db.init_db import init_db; init_db()")

echo ""
echo "安装完成。下一步："
echo "  1. 编辑 $APP_DIR/.env（ADMIN_TOKEN / CORS_ORIGINS / 模型 Key / OpenClaw）"
echo "  2. 启动后端：cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000"
echo "  3. 注册服务：sudo cp deploy/yongjie-panel.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now yongjie-panel"
echo "  4. 配置 nginx：见 docs/deployment.md 第 3.6 节"
