"""
main.py — 充电桩灵动岛监控应用入口

运行：
  python main.py

依赖：
  pip install PyQt5 requests
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

from charger_api import fetch_all_stations
from charger_ui import DynamicIsland, ISLAND_W

REFRESH_INTERVAL_MS = 30_000


# ══════════════════════════════════════════════════════════
#  后台数据线程
# ══════════════════════════════════════════════════════════
class DataWorker(QThread):
    data_ready  = pyqtSignal(dict)
    fetch_error = pyqtSignal(str)

    def run(self):
        try:
            data = fetch_all_stations()
            self.data_ready.emit(data)
        except Exception as e:
            self.fetch_error.emit(str(e))


# ══════════════════════════════════════════════════════════
#  应用控制器
# ══════════════════════════════════════════════════════════
class AppController:
    def __init__(self, island: DynamicIsland):
        self._island = island
        self._worker: DataWorker | None = None

        self._timer = QTimer()
        self._timer.timeout.connect(self._start_fetch)
        self._timer.start(REFRESH_INTERVAL_MS)

        # 启动立即拉取
        self._start_fetch()

    def _start_fetch(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = DataWorker()
        self._worker.data_ready.connect(self._on_data)
        self._worker.fetch_error.connect(self._on_error)
        self._worker.start()

    def _on_data(self, data: dict):
        total = sum(len(v) for v in data.values())
        free  = sum(o["status"] == 1 for v in data.values() for o in v)
        print(f"[✓] 刷新完成 — {len(data)} 站 / {total} 插座 / {free} 空闲")
        self._island.update_data(data)

    def _on_error(self, msg: str):
        print(f"[✗] 数据获取失败: {msg}")


# ══════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    island = DynamicIsland()

    screen = app.primaryScreen().availableGeometry()
    island.move((screen.width() - ISLAND_W) // 2, 60)
    island.show()

    controller = AppController(island)  # noqa: F841

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
