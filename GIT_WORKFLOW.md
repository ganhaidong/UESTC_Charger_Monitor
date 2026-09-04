# GitHub 引入与日常修改流程

本仓库已接入 GitHub（公开仓库 `ganhaidong/UESTC_Charger_Monitor`），日常改代码、发布到云服务器都通过 git 完成，不再手动 rsync。

## 一、当前仓库与远程

```bash
git remote -v
# origin    -> git@github.com:ganhaidong/UESTC_Charger_Monitor.git   （你的仓库，主）
# upstream  -> git@github.com:WGooold/UESTC_Charger_Monitor.git      （原作者，备用同步）
```

- 本地 Mac 是**唯一的编辑源头**；GitHub 是**版本记录 + 共享**；服务器是**运行环境**。
- `.gitignore` 已排除 `.venv`、`__pycache__`、`*.db*`、`.pyc`、`.DS_Store` 等运行时产物。
- 仓库体积已从历史 **856M 清理到 476K**（`git gc` 清除孤儿对象）。

## 二、三个“环境”的分工

| 环境 | 位置 | 作用 |
|---|---|---|
| 本地 Mac | `~/Dev/learning/UESTC_Charger_Monitor` | 开发、改代码、提交、推送 |
| GitHub | `github.com/ganhaidong/UESTC_Charger_Monitor` | 源码版本库、记录、回退、多端同步 |
| 服务器 | 见下 | 实际运行 |

服务器上的运行环境（**都不在 git 里，别动**）：
- `~/charger-monitor`：git 工作副本（`git pull` 更新的是这里）
- `/opt/charger-monitor`：运行副本（`deploy.sh` 把代码拷进来并跑服务）
- `/etc/charger-monitor.env`：**管理口令**（`CHARGER_AUTH_USER/PASS`、限流配置），只在服务器上
- `/opt/charger-monitor/charge_history/charge_history.db`：**已采样的数据**，保留 3 天

## 三、日常修改流程（一次标准更新）

### 第 1 步：改代码（本地 Mac）
在项目目录改完 `charge_history/`、`deploy/`、`web/` 等。

### 第 2 步：提交并推送（本地 Mac）
```bash
git add -A
git commit -m "这次改了啥：一句话说明"
git push -u origin master
```

### 第 3 步：服务器拉取并发布（云服务器）
```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@118.24.139.8
cd ~/charger-monitor && git pull && sudo bash deploy/deploy.sh
```
`deploy.sh` 会把最新代码同步到 `/opt` 并重启 systemd 服务 `charger-monitor`（开机自启、崩溃自动重启）。**数据库和 `/etc/charger-monitor.env` 不会被覆盖。**

### 第 4 步：验证
```bash
curl -sI http://127.0.0.1:8765/ | head -3          # Content-Type: text/html
curl -s -o /dev/null -w "health=%{http_code}\n" http://127.0.0.1:8765/api/health   # 200
systemctl status charger-monitor                  # active (running)
```

## 四、该提交 / 不该提交

- ✅ 提交：源码、`web/` 前端、`deploy/` 脚本、`station_locations.json`、配置/说明文档
- ❌ 不提交：`.venv/`、`__pycache__/`、`*.pyc`、**一切 `*.db*` 数据库**、**任何真实令牌/密钥/密码**、运行时数据

## 五、常用命令速查

| 目的 | 命令（本地 Mac） |
|---|---|
| 查看改动 | `git status` |
| 提交并推送到你的仓库 | `git add -A && git commit -m "说明" && git push -u origin master` |
| 查看历史 | `git log --oneline` |
| 回退到某版本 | `git checkout <commit>`（或 `git revert <commit>`） |
| 同步原作者最新改动 | `git pull upstream master && git push origin master` |
| 服务器更新 | `ssh ... && cd ~/charger-monitor && git pull && sudo bash deploy/deploy.sh` |

## 六、安全提醒（公开仓库）

1. **绝对不要**把真实令牌 / 密码 / 私钥提交到仓库。代码里的令牌一律用 `YOUR_TOKEN_HERE` 占位。
2. 历史中可能残留此前一个真实充电接口令牌 `issks_...`（来自原作者早期提交）；若你还用它采集，**建议去充电服务重新生成并作废旧令牌**。
3. 管理口令 `/etc/charger-monitor.env` 只在服务器上，**不提交**、不进仓库。
4. 想真正安全，建议后续给后端加 **HTTPS（Caddy 自动证书 + 你的域名）**，避免账号以明文传输。
