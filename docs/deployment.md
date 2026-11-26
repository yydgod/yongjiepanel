# 部署指南 · 永杰面板

面向生产环境的完整部署说明，覆盖宿主机部署、Docker Compose、反向代理与 HTTPS、备份恢复、升级与排障。
示例文件都在仓库的 [`deploy/`](../deploy) 目录，可直接复制修改。

---

## 1. 部署架构选择

| 方式 | 适用场景 | systemd 采集 | Docker 采集 | 复杂度 |
| --- | --- | --- | --- | --- |
| A. 宿主机（systemd + nginx） | 单机服务器、需要监控 systemd unit | ✅ | ✅ | 中 |
| B. Docker Compose | 快速上线、环境隔离、可重复部署 | ❌（容器内无 systemd） | ✅ | 低 |

> **重要**：采集调度与主机指标都保存在后端进程内（内存环形缓冲 + SQLite 配置），
> 因此后端必须以 **单 worker** 运行（`uvicorn ... --workers 1`，默认即 1），不要用 gunicorn 多进程。

两种方式的共同点：

- 后端监听 `127.0.0.1:8000`（或容器内 `8000`），由 nginx 统一对外
- 前端是纯静态产物（`frontend/dist`），由 nginx 托管，`/api/` 反向代理到后端
- 数据只需持久化 `backend/data/board.db`（SQLite，WAL 模式）与 `.env` 配置

---

## 2. 环境要求

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| 操作系统 | Linux（Debian/Ubuntu、TencentOS/CentOS 均可） | systemd 采集依赖宿主机 systemd |
| Python | ≥ 3.11（推荐 3.12） | FastAPI + Pydantic v2 |
| Node.js | ≥ 20 | 仅构建前端时需要，运行期不需要 |
| Docker | ≥ 24（可选） | 需要采集容器时安装，并保证 socket 可读 |
| 端口 | 8000（后端）、80/443（nginx） | 后端仅监听回环更安全 |
| 磁盘 | ≥ 2 GB（构建依赖 + 数据库 + 截图） | SQLite 本身占用很小 |

依赖安装示例：

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip nginx curl
# Node 20（NodeSource）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# TencentOS / CentOS / RHEL
sudo dnf install -y python3.11 python3.11-devel nginx curl
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs
```

---

## 3. 方式 A：宿主机部署（systemd + nginx）

### 3.1 创建运行用户与目录

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin yongjie
sudo mkdir -p /opt/yongjie-panel /var/www/yongjie-panel
sudo chown -R yongjie:yongjie /opt/yongjie-panel
```

### 3.2 拉取代码并安装

```bash
sudo -u yongjie -H bash
cd /opt/yongjie-panel
git clone <your-repo-url> .
# 或直接上传项目文件到 /opt/yongjie-panel

bash deploy/install.sh /opt/yongjie-panel
```

`deploy/install.sh` 会完成：校验 Python/Node 版本 → 创建 `.venv` → 安装后端依赖 →
`npm ci && npm run build` → 生成 `.env`（含随机 `SECRET_KEY`）→ 初始化数据库。
它**不会**做任何 `sudo` 操作，也不会覆盖已存在的 `.env`。

也可以手动执行：

```bash
cd /opt/yongjie-panel
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build
sudo mkdir -p /var/www/yongjie-panel
sudo cp -r dist/* /var/www/yongjie-panel/
cd .. && cp .env.example .env
```

### 3.3 配置 `.env`

```bash
# 生成随机 SECRET_KEY（用于加密模型 API Key）
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

vi /opt/yongjie-panel/.env
```

至少确认以下项：

```ini
APP_NAME=永杰面板
DATABASE_URL=sqlite:///./data/board.db
SECRET_KEY=<上一步生成的随机串>
ADMIN_TOKEN=<自定义强口令，启用写接口鉴权>
CORS_ORIGINS=https://panel.example.com
SYSTEMD_ENABLED=true
DOCKER_ENABLED=true
HOST_INTERVAL=3
# OpenClaw（可选）
OPENCLAW_BASE_URL=http://127.0.0.1:18789
OPENCLAW_TOKEN=oc_xxx
OPENCLAW_MODE=openai
# 模型 Key（也可在界面中配置）
DEEPSEEK_API_KEY=
HUNYUAN_API_KEY=
QWEN_API_KEY=
```

### 3.4 初始化数据库

```bash
cd /opt/yongjie-panel/backend
../.venv/bin/alembic upgrade head
# 首次启动也会自动建表并写入演示卡片（SEED_DEMO=true）
```

### 3.5 注册 systemd 服务

```bash
sudo cp deploy/yongjie-panel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yongjie-panel
sudo systemctl status yongjie-panel
```

服务默认 `WorkingDirectory=/opt/yongjie-panel/backend`，数据库会落在 `backend/data/board.db`。
若要采集 Docker，运行用户需能读取 `/var/run/docker.sock`：

```bash
sudo usermod -aG docker yongjie
sudo systemctl restart yongjie-panel
```

### 3.6 配置 nginx 并提供前端

```bash
sudo cp -r /opt/yongjie-panel/frontend/dist/* /var/www/yongjie-panel/
sudo cp deploy/nginx.conf /etc/nginx/conf.d/yongjie-panel.conf
sudo vi /etc/nginx/conf.d/yongjie-panel.conf   # 修改 server_name 与证书路径
sudo nginx -t && sudo systemctl reload nginx
```

`nginx.conf` 已包含：SPA history 回退、`/api/` 反代、**SSE 关闭缓冲**（Agent 流式对话必需）、静态资源长缓存。

### 3.7 验证

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/host/overview | head -c 200
systemctl status yongjie-panel
journalctl -u yongjie-panel -f
```

浏览器访问 `https://panel.example.com`，应看到「服务器总览」；`/board` 为卡片看板。

### 3.8 升级

```bash
cd /opt/yongjie-panel
sudo -u yongjie git pull
sudo -u yongjie .venv/bin/pip install -r backend/requirements.txt
(cd frontend && sudo -u yongjie npm ci && sudo -u yongjie npm run build)
sudo cp -r frontend/dist/* /var/www/yongjie-panel/
(cd backend && sudo -u yongjie ../.venv/bin/alembic upgrade head)
sudo systemctl restart yongjie-panel
```

> 升级前请先备份数据库（见第 7 节）。

---

## 4. 方式 B：Docker Compose

### 4.1 准备配置

```bash
git clone <your-repo-url> yongjie-panel
cd yongjie-panel
cp .env.example .env
# 修改 SECRET_KEY / ADMIN_TOKEN / CORS_ORIGINS / 模型 Key
```

### 4.2 启动

```bash
docker compose build
docker compose up -d
docker compose ps
curl -s http://127.0.0.1:8000/api/health
```

访问 `http://服务器IP:5173`（Compose 中前端 nginx 映射到宿主 5173，可按需改为 80）。

Compose 已做的关键配置：

- `backend` 挂载 `/var/run/docker.sock:ro`（只读，用于采集容器状态）
- 数据卷 `board-data` 持久化 SQLite
- `SYSTEMD_ENABLED=false`（容器内没有 systemd；需要该能力请用方式 A）
- 前端 nginx 关闭 `/api/` 缓冲以支持 SSE

### 4.3 查看日志与升级

```bash
docker compose logs -f backend
docker compose pull && docker compose build
docker compose up -d
```

### 4.4 数据备份（容器内）

```bash
docker compose exec backend python - <<'PY'
import sqlite3
src = sqlite3.connect('/data/board.db')
dst = sqlite3.connect('/data/backup.db')
src.backup(dst)
PY
docker compose cp backend:/data/backup.db ./board-backup.db
```

---

## 5. 反向代理与 HTTPS

推荐的站点配置（完整示例见 [`deploy/nginx.conf`](../deploy/nginx.conf)）：

```nginx
server {
    listen 80;
    server_name panel.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name panel.example.com;

    ssl_certificate     /etc/letsencrypt/live/panel.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/panel.example.com/privkey.pem;

    root /var/www/yongjie-panel;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;       # SSE 关键
        proxy_read_timeout 300s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

申请证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d panel.example.com
```

安全建议：

- 后端只监听 `127.0.0.1`，公网只暴露 443
- 启用 `ADMIN_TOKEN` 后，所有写请求（POST/PUT/PATCH/DELETE）需 `Authorization: Bearer <token>`；前端在 `localStorage.yongjie_admin_token` 中携带
- 若放公网，建议再加一层 IP 白名单或 VPN

---

## 6. 关键配置项

| 变量 | 默认 | 生产建议 |
| --- | --- | --- |
| `SECRET_KEY` | 开发占位值 | **必须替换为 32 字节随机串**；轮换后需重新录入模型 Key |
| `ADMIN_TOKEN` | 空 | 公网部署必须设置；留空表示不鉴权 |
| `CORS_ORIGINS` | localhost:5173 | 改为实际域名，如 `https://panel.example.com` |
| `DATABASE_URL` | `sqlite:///./data/board.db` | 保持默认（相对 `backend/`）；或用绝对路径 |
| `SEED_DEMO` | true | 生产可设 false，避免自动生成演示卡片 |
| `COLLECT_INTERVAL` | 5 | 服务卡片采集周期（秒） |
| `HOST_INTERVAL` | 3 | 首页主机指标采样周期（秒） |
| `HOST_HISTORY_POINTS` | 120 | 首页趋势点数（约 6 分钟） |
| `DOCKER_ENABLED` / `SYSTEMD_ENABLED` / `PORT_ENABLED` | true | 用不到的可关闭，减少无谓读取 |
| `ALLOW_MOCK_AI` | true | 生产建议 false：无 Key 时直接报错而不是演示回答 |
| `CHAT_MAX_TOOL_ROUNDS` | 4 | Agent 工具迭代上限 |
| `CONFIRM_TOKEN_TTL` | 300 | 破坏性操作确认令牌有效期（秒） |
| `OPENCLAW_*` | 空 | 不配置则直连供应商 |

完整的变量说明见 [`.env.example`](../.env.example)。

---

## 7. 备份与恢复

数据库是单文件 SQLite（WAL 模式），推荐使用 SQLite 在线备份（无需停服）：

```bash
bash deploy/backup.sh backend/data/board.db /var/backups/yongjie
# 产物：/var/backups/yongjie/board-YYYYmmdd-HHMMSS.db（默认保留 14 天）
```

定时任务（每天 03:30）：

```cron
30 3 * * * cd /opt/yongjie-panel && bash deploy/backup.sh backend/data/board.db /var/backups/yongjie >> /var/log/yongjie-backup.log 2>&1
```

**恢复**：

```bash
sudo systemctl stop yongjie-panel
cp /var/backups/yongjie/board-20261126-033000.db /opt/yongjie-panel/backend/data/board.db
rm -f /opt/yongjie-panel/backend/data/board.db-wal /opt/yongjie-panel/backend/data/board.db-shm
sudo chown yongjie:yongjie /opt/yongjie-panel/backend/data/board.db
sudo systemctl start yongjie-panel
```

同时备份 `.env`（含加密密钥，注意权限 600）；**丢失 `SECRET_KEY` 将无法解密已保存的模型 API Key**，需要在界面重新填写。

---

## 8. 监控与排障

健康检查端点：

```bash
curl -fsS http://127.0.0.1:8000/api/health          # 存活
curl -fsS http://127.0.0.1:8000/api/host/overview   # 主机指标（含 available 字段）
```

日志：后端输出结构化 JSON（自动脱敏 `api_key / authorization / token`）。

```bash
journalctl -u yongjie-panel -n 200 --no-pager
docker compose logs -n 200 backend
```

| 现象 | 原因 / 处理 |
| --- | --- |
| 502 Bad Gateway | 后端未启动或端口不符：`systemctl status yongjie-panel`、`curl 127.0.0.1:8000/api/health` |
| 首页正常但对话不流式 | nginx 未关闭 `proxy_buffering`，参考 `deploy/nginx.conf` |
| 卡片显示「无法连接 Docker」 | 运行用户不在 docker 组，或 socket 路径不同；可临时 `DOCKER_ENABLED=false` |
| systemd 卡片全部不可用 | 后端运行在容器内（无 PID 1 systemd），改用宿主机部署 |
| `database is locked` | 多个后端进程/worker 同时写 SQLite；确保单 worker，停止重复实例 |
| 模型配置后仍走演示通道 | `ALLOW_MOCK_AI=true` 且 Key 未生效；检查供应商「测试连通性」与 `.env` |
| 页面刷新 404 | nginx 缺少 `try_files $uri $uri/ /index.html` |
| 修改 `.env` 不生效 | 需 `systemctl restart yongjie-panel` / `docker compose up -d` |
| 主题偏好丢失 | 浏览器 localStorage 被清理；主题仅存本地，不跨设备 |

---

## 9. 验收清单

- [ ] `curl /api/health` 返回 `{"status":"ok"}`，`app` 名称为「永杰面板」
- [ ] 首页显示 CPU / 内存 / 磁盘 / 网络曲线，且 3 秒刷新
- [ ] 应用面板卡片显示真实状态（容器 / systemd / 端口按需）
- [ ] 卡片详情页 `/cards/:id` 可直接访问、刷新、切换 `?tab=chat`
- [ ] Agent 对话可流式输出（无 Key 时显示演示通道提示）
- [ ] 重启类操作弹出确认，执行后审计页有记录
- [ ] 明暗模式与主题色切换正常并被记住
- [ ] nginx 已启用 HTTPS，HTTP 自动跳转
- [ ] 备份脚本已加入 cron，且完成过一次恢复演练

---

## 10. 目录与权限参考

```text
/opt/yongjie-panel/            # 代码 + venv + .env（属主 yongjie，.env 600）
├── backend/data/board.db      # 业务数据（属主 yongjie）
├── frontend/dist/             # 构建产物
└── .venv/
/var/www/yongjie-panel/        # nginx 静态根目录（只读）
/var/backups/yongjie/          # 数据库备份（600，属主 yongjie）
```

```bash
sudo chmod 600 /opt/yongjie-panel/.env
sudo chown yongjie:yongjie /opt/yongjie-panel/.env
```
