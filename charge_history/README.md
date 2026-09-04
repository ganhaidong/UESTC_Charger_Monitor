# 充电历史库

这一套工具负责把 `all.json` 里的站点按分钟持续采样，形成最近三天的本地历史库，并提供查询界面。

## 目录

- `charge_history_backend.py`：采样后端和 HTTP 接口
- `charge_history_ui.py`：PyQt5 查询前端
- `charge_history_seed.py`：生成演示数据库
- `all.json`：站点清单
- `charge_history_demo.db`：演示数据
- `export_locations.py`：导出全部站点的地址/经纬度 → `station_locations.json`
- `web/`：手机网页前端（含地图页签）

## 站点位置标定（地图）

每个站点在充电接口里都带 `address + latitude/longitude`，可用于在真实地图上标定：
事先生成一次坐标表（121 站里 120 站有坐标，仅“综合楼电站 49790”需手动补）：

```powershell
python charge_history/export_locations.py
```

后端已提供 `GET /api/locations` 返回这份坐标表，网页“地图”页签读取并在地图上打点。
如需更换底图，改 `web/index.html` 顶部 `MAP` 配置：

- 默认 OpenStreetMap（WGS-84，需联网，代码里已自动做 GCJ-02→WGS-84 转换）：
  `tileUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"`，`gcjToWgs = true`
- 高德中文底图（GCJ-02 原生、无需转换，若被限流可换回）：
  `tileUrl = "https://wprd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}"`，`gcjToWgs = false`

## 本地运行

先启动后端：

```powershell
python charge_history/charge_history_backend.py
```

再启动前端：

```powershell
python charge_history/charge_history_ui.py
```

## 手机 / 浏览器访问（推荐）

后端自带一个移动端网页，电脑、手机浏览器打开即可用，无需装 App：

```powershell
python charge_history/charge_history_backend.py --host 0.0.0.0
```

- 本机打开：<http://127.0.0.1:8765/>
- 同一 Wi-Fi 的手机打开：`http://<电脑局域网IP>:8765/`（如 `http://192.168.1.103:8765/`）
- 网页源码在 `web/index.html`，托管逻辑在 `charge_history_backend.py` 的静态文件路由里

项目根目录还提供了双击启动脚本：

- macOS：双击 `start_server.command`
- Windows：双击 `start_server.bat`

## 演示数据

如果想先看界面效果，可以直接生成演示数据库：

```powershell
python charge_history/charge_history_seed.py
```

演示库默认写到当前目录下的 `charge_history_demo.db`，不会污染真实连续采样库。

## 常用调试命令

只采样前 5 个站点：

```powershell
python charge_history/charge_history_backend.py --station-limit 5
```

缩短采样间隔到 10 秒：

```powershell
python charge_history/charge_history_backend.py --sample-interval 10
```

只跑接口，不自动采样：

```powershell
python charge_history/charge_history_backend.py --db charge_history/charge_history_demo.db --no-collector
```

## 云服务器

部署到云服务器后，把前端顶部的后端地址改成：

```text
https://wgooold.cn:8765
```

注意：前端现在固定走 `https://wgooold.cn:8765`，所以后端必须满足下面两种方案之一：

- 方案 1：后端自己直接提供 HTTPS
- 方案 2：由 Nginx / Caddy 等反向代理在 `https://wgooold.cn:8765` 接入，再转发到本地 HTTP 后端

如果后端要自己直接对外监听 HTTPS，可以这样启动：

```powershell
python charge_history/charge_history_backend.py --host 0.0.0.0 --port 8765 --ssl-cert /path/to/fullchain.pem --ssl-key /path/to/privkey.pem
```

如果只是本地 HTTP 测试，对外监听可以这样启动：

```powershell
python charge_history/charge_history_backend.py --host 0.0.0.0
```

## 主要接口

- `GET /api/health`
- `GET /api/stations`
- `GET /api/outlets?station_id=120204`
- `GET /api/sessions?station_id=120204&outlet_no=O22071401189593&days=3`
- `GET /api/session?session_id=1`
- `GET /api/admin/collect`
