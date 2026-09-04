# 云端部署指南（腾讯云 / 阿里云）

后端**只依赖 `requests`**，不需要 PyQt5，跑裸 Python 即可，所以云上部署很轻。

## 0. 从零购买一台腾讯云轻量服务器（还没买的情况）

1. 注册/登录腾讯云，完成**实名认证**：<https://console.cloud.tencent.com/lighthouse>
2. 点「新建」→ 轻量应用服务器。
3. 选购参数：
   - **地域**：成都 / 广州（选国内地域即可，保证能访问充电接口 `wemp.issks.com`）
   - **镜像**：系统镜像 → **Ubuntu Server 24.04 LTS 64位**
   - **套餐**：2 核 2G 起步（121 站采样压力很小，够用；缺钱先 2C4G 亦可），带宽选固定带宽即可
4. 设置登录方式：**SSH 密钥**（推荐）或**密码**，记下或保存。
5. 购买完成后，在控制台记下**公网 IP**。
6. 放行端口：进入该实例 →「防火墙」→「添加规则」：
   - 协议 **TCP**，端口 **8765**，来源 `0.0.0.0/0`，允许
   - （SSH 22 一般默认已放行）

> 若实在想在手机上先验证，也可先用免费版/按量计费，跑通后再续。

## 1. 选服务器

| 项 | 建议 |
|---|---|
| 云厂商 | 腾讯云 LightHouse / 阿里云 ECS（国内地域，如成都、广州） |
| 配置 | 2C2G 足够（121 站每秒并发采样，压力很小） |
| 系统 | Ubuntu 22.04 / 24.04（脚本专为 Ubuntu/Debian 设计） |
| 注意 | 选**国内地域**，避免充电接口 `wemp.issks.com` 对境外 IP 的访问限制 |

## 2. 放行端口

- 腾讯云：控制台 → 防火墙 → 添加规则，放行 **TCP 8765**（入站）。
- 阿里云：安全组 → 入方向 → 放行 **TCP 8765**。

## 3. 把项目传到服务器（二选一）

```bash
# 方式 A：git
git clone <你的仓库地址> /home/ubuntu/charger-monitor
# 方式 B：本机 scp（在你自己电脑上执行，<服务器IP> 换成公网 IP，-i 换成你的私钥文件）
scp -i <私钥文件> -r ./UESTC_Charger_Monitor ubuntu@<服务器IP>:/home/ubuntu/charger-monitor
```

## 4. 一键部署（在服务器上执行）

```bash
cd ~/charger-monitor
sudo bash deploy/deploy.sh
```

脚本会：
- 安装 `python3`、`venv`、`rsync`；
- 把代码装到 `/opt/charger-monitor`，建 `charger` 用户；
- 建虚拟环境装 `requests`；
- 注册并启动 systemd 服务 `charger-monitor`（**开机自启 + 崩溃自动重启**）。

## 5. 验证

```bash
curl http://127.0.0.1:8765/api/health
systemctl status charger-monitor
```

手机浏览器打开：`http://<服务器IP>:8765/` → 点「地图」查位置、「列表」筛选空闲。

> 服务器上的站点列表是 `all.json`（已在 `/opt/charger-monitor/charge_history/all.json`）。首次启动会自动采样建库，约 1 分钟后就有数据。

## 6. 让链接更好看 / 加 HTTPS（Caddy 反向代理，推荐）

用 Caddy 反代，可以把 `http://118.24.139.8:8765/` 变成 **`http://118.24.139.8/`**（去掉端口），或配域名后变 **`https://你的域名/`**（自动 HTTPS）。仓库里已给模板 `deploy/Caddyfile.example`。

```bash
sudo apt install -y caddy
sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
# 按需取消注释 Caddyfile 里“方案一(纯IP走80)”或“方案二(域名+HTTPS)”那段，改好域名
sudo nano /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

- **只用 IP**：放行端口 **80**；链接变成 `http://118.24.139.8/`。
- **域名 + HTTPS**：放行端口 **80、443**；把域名 A 记录解析到 `118.24.139.8`；Caddy 自动申请并续期证书，链接变成 `https://你的域名/`。

> 启用 Caddy 后，建议把后端改为只监听本机，避免 `8765` 仍明文暴露：
> 编辑 `deploy/charger-monitor.service` 的 `ExecStart` 把 `--host 0.0.0.0` 改成 `--host 127.0.0.1`，然后
> `sudo systemctl daemon-reload && sudo systemctl restart charger-monitor`。
> 之后防火墙只放行 80/443（IP 模式）或只 443（域名模式）。

## 7. 更新部署

代码更新后在服务器上重新执行一次 deploy.sh 即可（脚本保留服务器上的数据库，会增量同步代码）：

```bash
cd ~/charger-monitor && git pull
sudo bash deploy/deploy.sh
```

## 8. 数据与注意

- 数据库在 `/opt/charger-monitor/charge_history/charge_history.db`（保留 3 天，自动清理）。
- 坐标表 `/opt/charger-monitor/charge_history/station_locations.json`；加站后可重跑 `export_locations.py` 再 `sudo systemctl restart charger-monitor`。
- 安全模型（面向大量用户）：
  - **查询类接口全开放、无需登录**：网页 `/`、`/api/health`、`/api/stations`、`/api/outlets`、`/api/sessions`、`/api/session`、`/api/locations` 任何人可访问，方便大家查桩。
  - **`/api/admin/collect`（手动采样）需管理口令**：`deploy.sh` 会生成 `/etc/charger-monitor.env` 模板，填好 `CHARGER_AUTH_USER`/`CHARGER_AUTH_PASS` 后重启即生效；**未配置口令时该接口直接 403 关闭**（避免公网被随意触发）。
  - **按 IP 限流**：默认每 IP 每 60 秒 600 次请求（`CHARGER_RATE_LIMIT`，`CHARGER_RATE_WINDOW`），超过返回 429；校内多人共用出口 IP 时建议保持宽松或设 0 关闭。

  ```bash
  # 编辑 /etc/charger-monitor.env，改成自己的账号密码（可选调限流阈值）
  sudo nano /etc/charger-monitor.env
  sudo systemctl restart charger-monitor
  ```

- 手动触发一次采样（需口令）：`curl -u 账号:密码 http://<IP>:8765/api/admin/collect`。
- 默认（本地/未配 env）：查询全开放，`/api/admin/collect` 返回 403。
