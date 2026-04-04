# Charge Tools

项目已经按工具拆成三个目录：

- [`charger_monitor`](/D:/charge/charger_monitor)：桌面悬浮监控主程序
- [`station_picker`](/D:/charge/station_picker)：站点查询、导出和快速扫描工具
- [`charge_history`](/D:/charge/charge_history)：三天历史库后端、前端和演示数据

公共依赖文件保留在根目录：

- [`requirements.txt`](/D:/charge/requirements.txt)

## 常用入口

监控主程序：

```powershell
python charger_monitor\main.py
```

站点选择器：

```powershell
python station_picker\station_picker.py
```

三天历史库后端：

```powershell
python charge_history\charge_history_backend.py
```

三天历史库前端：

```powershell
python charge_history\charge_history_ui.py
```
