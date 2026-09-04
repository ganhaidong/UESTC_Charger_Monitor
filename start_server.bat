@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo 启动充电桩后端，监听 0.0.0.0:8765（局域网内手机可访问）
echo 停止请按 Ctrl+C 或关闭本窗口
start "" http://127.0.0.1:8765/
"%PY%" charge_history\charge_history_backend.py --host 0.0.0.0
pause
