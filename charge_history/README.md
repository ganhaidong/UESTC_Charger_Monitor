# 充电历史库

这一套工具负责把 `all.json` 里的站点按分钟持续采样，形成最近三天的本地历史库，并提供查询界面。

## 目录

- `charge_history_backend.py`：采样后端和 HTTP 接口
- `charge_history_ui.py`：PyQt5 查询前端
- `charge_history_seed.py`：生成演示数据库
- `all.json`：站点清单
- `charge_history_demo.db`：演示数据

## 本地运行

先启动后端：

```powershell
python charge_history/charge_history_backend.py
```

再启动前端：

```powershell
python charge_history/charge_history_ui.py
```

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
