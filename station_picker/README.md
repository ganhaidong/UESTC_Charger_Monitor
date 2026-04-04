# 站点查询工具

这一组目录放的是站点选择和快速扫描相关脚本。

## 目录

- `station_picker.py`：附近站点查询并导出 `station.json`
- `station_picker.spec`：站点选择器打包配置
- `charge.py`：基于固定站点列表的快速空闲插座扫描脚本

## 运行

站点选择器：

```powershell
python station_picker/station_picker.py
```

快速扫描：

```powershell
python station_picker/charge.py
```
