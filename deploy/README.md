# deploy/ 部署示例

完整步骤见 [docs/deployment.md](../docs/deployment.md)，这里只列出文件用途：

| 文件 | 用途 |
| --- | --- |
| `install.sh` | 项目目录内一键安装：校验版本 → venv → 依赖 → 前端构建 → 生成 `.env` → 初始化数据库（不使用 sudo） |
| `yongjie-panel.service` | 宿主机 systemd 单元（单 worker、只读系统目录、可选 docker 组） |
| `nginx.conf` | nginx 站点示例：HTTPS、SPA 回退、`/api/` 反代、SSE 关闭缓冲、静态缓存 |
| `backup.sh` | SQLite 在线备份，默认保留 14 天，可加入 cron |

快速使用：

```bash
bash deploy/install.sh /opt/yongjie-panel
sudo cp deploy/yongjie-panel.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now yongjie-panel
sudo cp deploy/nginx.conf /etc/nginx/conf.d/yongjie-panel.conf
sudo nginx -t && sudo systemctl reload nginx
bash deploy/backup.sh backend/data/board.db /var/backups/yongjie
```
