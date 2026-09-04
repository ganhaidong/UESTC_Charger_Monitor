# charge_history（核心模块）

这个目录是**整个项目的主体**：后端采样 + 历史库 + HTTP 接口 + 手机网页前端。

## 文件说明

| 文件 | 作用 |
|---|---|
| `charge_history_backend.py` | 后端主程序：每 60 秒采样所有站 → 写入 SQLite 历史库，并提供 HTTP 接口、托管网页 |
| `charger_api.py` | 调「闪开来电」(issks) 接口取站点/插座数据 |
| `all.json` | 站点清单（`站点名 -> station_id`） |
| `station_locations.json` | 各站经纬度 + 地址（用于地图定位） |
| `station_overrides.json` | 手动坐标校正（可选；源数据个别站坐标错时用） |
| `export_locations.py` | 生成 / 刷新 `station_locations.json` |
| `web/` | 手机网页前端（`index.html` + 本地 Leaflet 地图库） |

## 接口一览

- `GET /api/health` — 健康状态
- `GET /api/stations` — 站点列表（空闲/充电中/故障汇总）
- `GET /api/outlets?station_id=` — 某站插座
- `GET /api/sessions?station_id=&outlet_no=` — 某插座历史
- `GET /api/session?session_id=` — 会话详情
- `GET /api/locations` — 站点坐标
- `GET /api/admin/collect` — 手动触发一次采样（需管理口令）

## 运行

```bash
python charge_history_backend.py --host 0.0.0.0
```
