#!/bin/bash
# 双击启动后端 + 自动打开手机版网页（macOS）
cd "$(dirname "$0")" || exit 1

if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    echo "未找到 Python，请先安装依赖：pip install -r requirements.txt"
    read -r -p "按回车退出..."
    exit 1
fi

# 等 2 秒后自动打开本机浏览器
(sleep 2; open "http://127.0.0.1:8765/") &

echo "启动充电桩后端，监听 0.0.0.0:8765（局域网内手机可访问）"
echo "停止请按 Ctrl+C 或关闭本窗口"
exec "$PY" charge_history/charge_history_backend.py --host 0.0.0.0
