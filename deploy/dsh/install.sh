#!/usr/bin/env bash
# 安装并构建 dsh（DeepSeek Harness）fork，供永杰面板调用。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${DSH_REPO:-https://github.com/deepseek-ai/deepseek-harness.git}"
TAG="${DSH_TAG:-dsh-v0.2.2-rc.5}"
DSH_DIR="${DSH_DIR:-/opt/yongjie-dsh}"
DSH_HOME="${DSH_HOME:-/data/yongjie/dsh-home}"
WORKSPACES="${WORKSPACES:-/data/workspaces}"
PATCH="$SCRIPT_DIR/patches/yongjie-cards.patch"

echo "==> 检查运行时"
command -v node >/dev/null || { echo "缺少 node（需要 >= 24.9）"; exit 1; }
node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>24||(a===24&&b>=9)?0:1)' \
  || { echo "Node 版本过低：$(node -v)，需要 >= 24.9"; exit 1; }
command -v git >/dev/null || { echo "缺少 git"; exit 1; }

echo "==> 获取 dsh 源码（$TAG）"
if [ ! -d "$DSH_DIR/.git" ]; then
  mkdir -p "$(dirname "$DSH_DIR")"
  git clone --depth 1 --branch "$TAG" "$REPO" "$DSH_DIR"
else
  git -C "$DSH_DIR" fetch --depth 1 origin tag "$TAG"
  git -C "$DSH_DIR" checkout -q FETCH_HEAD
fi

echo "==> 应用永杰面板补丁"
if git -C "$DSH_DIR" apply --check "$PATCH" 2>/dev/null; then
  git -C "$DSH_DIR" apply "$PATCH"
elif git -C "$DSH_DIR" apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "补丁已应用，跳过"
else
  echo "补丁无法应用，请检查 dsh 版本是否仍为 $TAG"
  exit 1
fi

echo "==> 安装 pnpm 11.28.5"
corepack enable
corepack prepare pnpm@11.28.5 --activate
export PATH="$(dirname "$(command -v node)"):$PATH"

echo "==> 安装依赖（约 2GB，首次较慢）"
cd "$DSH_DIR"
pnpm install --frozen-lockfile

echo "==> 构建 dsh（host + client + web）"
pnpm run build

echo "==> 准备运行目录"
mkdir -p "$DSH_HOME" "$WORKSPACES" /data/yongjie
install -m 755 "$SCRIPT_DIR/start.sh" "$DSH_DIR/start.sh"

cat <<EOF

安装完成。

下一步：
  1. 编辑 /etc/systemd/system/yongjie-dsh.service（按实际路径/用户）
  2. sudo systemctl daemon-reload && sudo systemctl enable --now yongjie-dsh
  3. 查看 /data/yongjie/dsh.log，确认 token 已写入 /data/yongjie/dsh-token
  4. 面板 .env：
       DSH_BASE_URL=http://127.0.0.1:3082
       DSH_PUBLIC_URL=https://dsh.example.com
       DSH_TOKEN_FILE=/data/yongjie/dsh-token
       DSH_CARDS_STORE=$DSH_HOME/storages/yongjie-cards.json
  5. 重启面板后端，打开 dsh 页签完成模型配置

dsh 目录：$DSH_DIR
数据目录：$DSH_HOME
工作区：  $WORKSPACES
EOF
