# 充电桩监控

桌面悬浮式充电站监控工具，主入口是 `main.py`。

## 目录

- `main.py`：主程序入口
- `charger_api.py`：站点和插座数据获取
- `charger_ui.py`：监控界面
- `station.json`：主程序读取的站点配置
- `charger_monitor.spec`：主程序打包配置

## 运行

从项目根目录运行：

```powershell
python charger_monitor/main.py
```

## 配置

- `station.json` 需要和主程序脚本或打包后的 `exe` 放在同一目录
- 充电日志会自动写到主程序同目录下的 `charge_logs/`

## 打包

主程序：

```powershell
pyinstaller charger_monitor/charger_monitor.spec
```

站点选择器：

```powershell
pyinstaller station_picker/station_picker.spec
```

## 相关工具

- `../station_picker/`
- `../charge_history/`
