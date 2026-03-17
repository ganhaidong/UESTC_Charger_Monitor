# 充电桩监控

一个仿苹果 Dynamic Island 风格的充电桩实时状态监控工具，悬浮在桌面顶部，随时查看附近充电站的插座占用情况，并支持充电过程的实时监控与功率曲线记录。

---

## 软件包文件

| 文件 | 说明 |
|------|------|
| `充电桩监控.exe` | 主程序，桌面悬浮式充电桩实时监控 |
| `充电桩ID搜索器.exe` | 辅助工具，查询附近充电站并生成配置文件 |
| `station.json` | 站点配置文件，须与主程序放在同一目录下 |

> `station.json` 必须与主程序在同一目录，否则启动时报错。

---

## 首次使用

1. 运行 `充电桩ID搜索器.exe`，查询附近充电站
2. 勾选需要监控的站点，点击「导出 station.json」
3. 将导出的 `station.json` 放入与 `充电桩监控.exe` 相同的文件夹
4. 双击运行 `充电桩监控.exe`，屏幕顶部出现黑色胶囊即为启动成功

---

## 主要功能

- **胶囊状态**：绿色指示灯表示有空闲插座，红色表示全部占用，右侧显示空闲数/总数
- **详情面板**：单击胶囊展开，显示各站点全部插座状态及充电数据（功率/费用/时长）
- **搜索过滤**：面板顶部搜索栏，按站点名称实时过滤
- **排序**：工具栏右侧排序按钮，支持按序号/功率/费用/时长排列插座
- **我的插座**：点击占用中的插座行左滑，标记为「我的插座」后进入充电监控模式，胶囊实时显示功率/费用/时长，并有绿色扫光动画
- **充电结束判断**：通过基线功率检测算法自动判断正常结束（绿色「充电完成」）或异常结束（红色「充电异常结束」），异常条件为末尾功率仍处高位或下降段过短（疑似突然断电/人为拔枪）
- **充电功率曲线**：充电过程中按固定间隔采样功率数据，可通过左键菜单查看内嵌曲线视图，支持左右拖拽滑动查看历史数据，曲线上实时绘制基线功率参考线（黄色虚线）
- **充电日志**：每次充电自动保存 JSON 日志到 `charge_logs/` 目录，记录每个采样点的时间/功率/费用，及充电结束时的统计摘要
- **拖动**：右键胶囊 → 拖动模式，可将胶囊拖到任意位置

---

## 充电日志格式

日志保存在程序同目录的 `charge_logs/` 文件夹，文件名格式：`charge_YYYYMMDD_HHMMSS_outlet<序号>.json`

```json
{
  "start_time": "2025-03-17T14:30:22",
  "outlet_no": "ABC123",
  "serial": 5,
  "result": "normal",
  "end_time": "2025-03-17T16:45:10",
  "points": [
    { "time": "14:30:22", "used_min": 12, "power_w": 330, "fee": 0.85 }
  ],
  "summary": {
    "total_points": 42,
    "max_power_w": 350,
    "avg_power_w": 218.3,
    "duration_min": 128,
    "final_fee": 14.26
  }
}
```

`result` 字段取值：`normal`（正常充满）/ `abnormal`（异常结束）/ `manual_exit`（手动退出监控）/ `in_progress`（充电中）

---

## 源码目录结构

```
charger_monitor/
├── main.py                 # 应用入口
├── charger_api.py          # 数据获取层
├── charger_ui.py           # UI 组件层（含充电监控、曲线、日志）
├── station_picker.py       # 站点查询工具
├── station.json            # 站点配置（运行时从外部读取）
├── icons.qrc               # Qt 图标资源描述（可选）
├── icons_rc.py             # 编译后的图标模块（可选，需自行生成）
├── charger_monitor.spec    # 主程序打包配置
├── station_picker.spec     # 搜索器打包配置
├── requirements.txt        # Python 依赖
└── README.md
```

---

## 开发环境

- Python 3.8+
- 依赖：`pip install -r requirements.txt`（PyQt5、requests）

---

## 打包

```bash
# 主程序 → 充电桩监控.exe
pyinstaller charger_monitor.spec

# 搜索器 → 充电桩ID搜索器.exe
pyinstaller station_picker.spec
```

打包产物在 `dist/` 目录，发布时将 `station.json` 放在 exe 同目录即可。`charge_logs/` 目录会在首次进入充电监控模式时自动创建。

---

## 可调参数

| 文件 | 常量 | 默认值 | 说明 |
|------|------|--------|------|
| `main.py` | `REFRESH_INTERVAL_MS` | `30000` | 数据刷新间隔（毫秒）|
| `charger_ui.py` | `POWER_LOG_INTERVAL_S` | `30` | 功率采样间隔（秒），正式使用建议改为 `120` |

---

## 自定义图标（可选）

在 `charger_ui.py` 顶部填入图标路径常量（`CHARGE_ICON_PATH`、`SORT_ICON_PATH` 等），准备好 PNG 后用 `pyrcc5 icons.qrc -o icons_rc.py` 编译并取消顶部 `import icons_rc` 的注释。路径留空时自动回退到文字符号，功能不受影响。

---

## 常见问题

**胶囊透明/不可见** — 开启系统透明效果（Windows：设置 → 个性化 → 颜色 → 透明效果）。

**一直显示「正在获取数据…」** — 检查网络连接及 `station.json` 中的站点 ID 是否有效。

**打包后闪退** — 命令行运行 exe 查看报错，常见原因是缺少 Qt 平台插件，将 `PyQt5/Qt5/plugins/platforms/` 复制到 exe 同目录下。

**charge_logs 目录在哪** — 与 `充电桩监控.exe` 同目录，首次进入充电监控模式时自动创建。
