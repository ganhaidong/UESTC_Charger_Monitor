# UESTC 充电桩监控工具（Charge Tools）

面向电子科技大学清水河校区的**充电桩状态查询与历史记录**工具集。核心能力：

- **手机/电脑浏览器访问**：页面上「列表」快速筛空闲、「地图」看每个站的位置和空闲情况、「历史」查近 3 天充电会话与功率曲线。
- **站点点位标定**：利用充电接口自带的地址 + 经纬度，把全校站点画到真实地图上（高德中文底图），无需人工手绘。
- **桌面悬浮监控**（可选）：PyQt5 桌面悬浮窗，实时显示各站空闲插座数。

数据来源为充电桩服务接口（`wemp.issks.com`），本工具把全部站点按分钟采样，写入本地 SQLite 保留 3 天。

## 目录结构

| 目录 | 说明 |
|---|---|
| [`charge_history/`](charge_history/) | **主程序**：采样后端 + SQLite 历史库 + HTTP 接口 + 手机网页前端 |
| [`charger_monitor/`](charger_monitor/) | 桌面悬浮监控（可选，需 PyQt5） |
| [`station_picker/`](station_picker/) | 附近站点查询/导出 `station.json`（可选，需 PyQt5） |
| [`deploy/`](deploy/) | 云服务器一键部署（systemd + venv + deploy.sh） |
| [`GIT_WORKFLOW.md`](GIT_WORKFLOW.md) | GitHub 接入与日常修改流程 |

根目录 `requirements.txt`：`PyQt5`（仅桌面工具需要）+ `requests`（后端必需）。

## 快速开始（推荐：网页版）

后端只依赖 `requests`，无需 PyQt5。

```bash
# 安装依赖（最好用 venv）
pip install -r requirements.txt        # 或只装 requests：pip install requests

# 1) 生成站点点位坐标表（首次/加站后执行一次）
python charge_history/export_locations.py

# 2) 启动后端（默认监听 127.0.0.1:8765；要局域网/手机访问用 --host 0.0.0.0）
python charge_history/charge_history_backend.py --host 0.0.0.0
```

- 本机打开：<http://127.0.0.1:8765/>
- 同一 Wi-Fi 的手机打开：`http://<电脑IP>:8765/`

页面上：
- **列表**：顶栏 [全部 / 空闲 / 充电中] 一键筛选；点站点 → 插座（空闲/充电中/故障）→ 会话历史 → 功率曲线图。
- **地图**：全部站点点位（同址自动合并为一个标记，弹窗列出该点所有站点），绿=有空闲，红=全副，点「查看插座」直接进入该站。
- 支持 30 秒自动刷新开关。

> 也可双击根目录的 `start_server.command`（macOS）或 `start_server.bat`（Windows）一键启动并自动打开浏览器。

## 配置

- **站点清单**：`charge_history/all.json`（共用站点），监控主程序读 `charger_monitor/station.json`。都是 `站点名 -> station_id` 结构。
- **管理口令 & 限流**：`/etc/charger-monitor.env`（云服务器用）设置 `CHARGER_AUTH_USER`/`CHARGER_AUTH_PASS` 保护 `/api/admin/collect`，`CHARGER_RATE_LIMIT` 做按 IP 限流。**查询接口默认全开放、无需登录**。

## 云部署（腾讯云/阿里云）

后端很轻（只需 `requests`），`deploy.sh` 一键装环境、建 systemd 服务（开机自启 + 崩溃重启）。详见 [`deploy/README.md`](deploy/README.md)。

```bash
# 把仓库放到服务器后：
sudo bash deploy/deploy.sh
```

## 版本管理 & 日常修改流程

已接入 GitHub（`ganhaidong/UESTC_Charger_Monitor`，公开）。改代码：`git add -A && git commit -m "..." && git push`；服务器：`git pull && sudo bash deploy/deploy.sh`。详见 [`GIT_WORKFLOW.md`](GIT_WORKFLOW.md)。

## 安全提醒

- 仓库为公开仓库，**切勿提交任何真实令牌 / 密码 / 密钥**（一律用占位符）。
- 管理口令 `/etc/charger-monitor.env` 只在服务器上，不进仓库。
- 若要对公网更安全，建议后续加 **HTTPS**（Caddy 自动证书）。
