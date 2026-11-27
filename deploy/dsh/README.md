# dsh 集成部署

永杰面板本身不再包含模型与 Agent；卡片对话、文件、终端由 dsh 原生工作区提供。

## 目录

| 文件 | 用途 |
| --- | --- |
| `install.sh` | 克隆固定版本 dsh、应用永杰补丁、安装依赖并完整构建 |
| `start.sh` | 启动 dsh web，提取启动 token 写入面板可读文件 |
| `yongjie-dsh.service` | systemd 单元示例 |
| `patches/yongjie-cards.patch` | 卡片首页、常驻工作区入口、`?workspace=` 深链与登录跳转保留参数 |
| `../nginx-dsh.conf` | dsh 独立子域名反代示例 |

## 1. 安装

```bash
# Node >= 24.9、pnpm 11、git
sudo mkdir -p /opt/yongjie-dsh /data/yongjie /data/workspaces
sudo chown -R yongjie:yongjie /opt/yongjie-dsh /data/yongjie /data/workspaces

sudo -u yongjie DSH_DIR=/opt/yongjie-dsh \
  bash deploy/dsh/install.sh
```

安装完成后 dsh 源码位于 `/opt/yongjie-dsh`，数据目录 `/data/yongjie/dsh-home`。

## 2. 启动

```bash
sudo cp deploy/dsh/yongjie-dsh.service /etc/systemd/system/
# 修改 User / DSH_PUBLIC_URL / DSH_TOKEN_FILE
sudo systemctl daemon-reload
sudo systemctl enable --now yongjie-dsh
```

`start.sh` 会把 dsh 启动日志里的 token 写入 `/data/yongjie/dsh-token`（权限 600）。
面板通过 `DSH_TOKEN_FILE` 动态读取，因此 **dsh 重启后不需要重启面板**。

## 3. 面板配置

```ini
DSH_BASE_URL=http://127.0.0.1:3082
DSH_PUBLIC_URL=https://dsh.example.com
DSH_TOKEN_FILE=/data/yongjie/dsh-token
DSH_CARDS_STORE=/data/yongjie/dsh-home/storages/yongjie-cards.json
```

- `DSH_BASE_URL` 是后端/本机访问地址。
- `DSH_PUBLIC_URL` 是浏览器访问地址，必须能从用户浏览器打开；本地开发可留空回退 `DSH_BASE_URL`。
- 重启面板后端后，打开顶部「dsh 工作区」页签。

## 4. 初始化工作区

```bash
cd /opt/yongjie-panel   # 面板仓库目录
sudo -u yongjie .venv/bin/python scripts/migrate_cards_to_workspaces.py \
  --dsh-home /data/yongjie/dsh-home \
  --workspaces /data/workspaces
```

脚本会创建 `/data/workspaces/<card-id>`、写入 dsh 工作区注册表，并生成
`yongjie-cards.json`。执行前建议先停 dsh，避免注册表并发写。

## 5. 配置模型

首次打开 dsh 工作区会提示登录/添加 API Key：

1. 打开 `https://dsh.example.com/?token=<token>`（或面板 dsh 页签）
2. Settings → Models → Add model provider → Custom model API
3. 填 Base URL / API Key / Model ID（例如混元 `hy4-flash`）
4. 在会话输入框选择该模型

模型完全由 dsh 管理，面板不保存 Key。

## 6. nginx

```bash
sudo cp deploy/nginx-dsh.conf /etc/nginx/conf.d/yongjie-dsh.conf
# 修改 server_name / 证书 / 面板域名
sudo nginx -t && sudo systemctl reload nginx
```

必须能在浏览器打开 `DSH_PUBLIC_URL`；如果只用 `127.0.0.1:3082`，远程浏览器会把 iframe 指向自己的本机，导致打不开。

## 7. 升级

```bash
sudo systemctl stop yongjie-dsh
sudo -u yongjie DSH_DIR=/opt/yongjie-dsh DSH_TAG=dsh-v0.2.2-rc.5 \
  bash deploy/dsh/install.sh
sudo systemctl start yongjie-dsh
```

dsh 处于 Developer Preview，升级前先在测试环境验证补丁是否仍可应用。
