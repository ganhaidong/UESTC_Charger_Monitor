#!/usr/bin/env bash
# 一键在 Ubuntu/Debian 云服务器上部署「充电桩后端」
# 用法：把项目上传到服务器后，在项目根目录执行：
#     sudo bash deploy/deploy.sh
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/charger-monitor
SERVICE=charger-monitor   # systemd 服务名（unit 文件名）
RUN_USER=charger          # 实际运行的系统用户（与服务文件里的 User= 保持一致）

command -v rsync >/dev/null 2>&1 || { echo "缺少 rsync，请先安装：sudo apt-get install -y rsync"; exit 1; }

echo "==> [1/6] 安装系统依赖 (python3 + venv + rsync)"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip rsync

echo "==> [2/6] 创建应用目录与运行用户"
sudo useradd -r -s /usr/sbin/nologin "$RUN_USER" 2>/dev/null || true
sudo mkdir -p "$APP_DIR"

echo "==> [3/6] 拷贝代码到 $APP_DIR（排除本地数据库与缓存，保留服务器已有数据）"
sudo rsync -a --exclude '*.db' --exclude '*.db-*' --exclude '__pycache__' \
  "$SRC_DIR/charge_history/" "$APP_DIR/charge_history/"

echo "==> [4/6] 创建虚拟环境并安装依赖（后端仅需 requests，无需 PyQt5）"
if [ ! -d "$APP_DIR/.venv" ]; then
  sudo python3 -m venv "$APP_DIR/.venv"
fi
sudo cp "$SRC_DIR/deploy/requirements.txt" "$APP_DIR/charge_history/requirements.txt"
sudo "$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
sudo "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/charge_history/requirements.txt"

echo "==> [5/6] 安装并启动 systemd 服务（开机自启 + 崩溃自动重启）"
sudo cp "$SRC_DIR/deploy/charger-monitor.service" "/etc/systemd/system/$SERVICE.service"
sudo chown -R "$RUN_USER:$RUN_USER" "$APP_DIR"

# 访问口令模板：若尚不存在则创建，用户可编辑后重启服务启用 Basic 鉴权
if [ ! -f /etc/charger-monitor.env ]; then
  sudo tee /etc/charger-monitor.env >/dev/null <<'EOF'
# 管理口令：仅作用于 /api/admin/*（如 /api/admin/collect 手动采集）。
#   查询接口/网页/地图 永远免费开放、无需登录。把下面两行改成你自己的后重启服务生效。
CHARGER_AUTH_USER=admin
CHARGER_AUTH_PASS=change_me

# （可选）按 IP 限流：每 IP 每 60 秒允许的请求数，默认 600；设为 0 表示不限。
#   注意：若校内很多人共用同一出口 IP，限得太后会误伤，建议保持 600 或更宽松。
#CHARGER_RATE_LIMIT=600
#CHARGER_RATE_WINDOW=60
EOF
  sudo chmod 600 /etc/charger-monitor.env
  echo "==> 已生成配置模板 /etc/charger-monitor.env（填好账号密码后重启服务生效）"
fi
# 让代码/网页可读、目录可进入；但绝不能动 .venv 里 python/pip 的可执行权限！
sudo find "$APP_DIR/charge_history" -type d -exec chmod 755 {} \;
sudo find "$APP_DIR/charge_history" -type f -exec chmod 644 {} \;
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

echo "==> [6/6] 完成，服务状态："
sudo systemctl status "$SERVICE" --no-pager || true
echo
echo "本机健康检查：curl http://127.0.0.1:8765/api/health"
echo "外网访问　　：http://<服务器IP>:8765/"
echo "手机网页　　：http://<服务器IP>:8765/   （同一站点清单自动采样）"
