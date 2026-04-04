"""
station_picker.py — 附近充电站查询 & station.json 导出工具

使用方式：
  python station_picker.py

启动后自动查询附近充电站，勾选后导出 station.json 供主程序使用。
"""

import sys
import json
import requests

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QCheckBox,
    QAbstractItemView, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QPainterPath

# ══════════════════════════════════════════════════════════
#  API 配置
# ══════════════════════════════════════════════════════════
HEADERS = {
    "sec-ch-ua-platform": "\"Android\"",
    "sec-ch-ua": "\"Chromium\";v=\"142\", \"Android WebView\";v=\"142\", \"Not_A Brand\";v=\"99\"",
    "systemphone": "Android 16",
    "sec-ch-ua-mobile": "?1",
    "brands": "2407FRK8EC",
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 16; 2407FRK8EC Build/BP2A.250605.031.A3; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36"
    ),
    "content-type": "application/json;charset=utf-8",
    # "token": "YOUR_TOKEN_HERE",
    "accept": "*/*",
    "origin": "https://api.issks.com",
    "x-requested-with": "com.tencent.mm",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://api.issks.com/",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

NEAR_STATION_URL = "https://wemp.issks.com/device/v1/near/station"

# 固定查询 payload
PAYLOAD = {
    "page": 1,
    "pageSize": 200,
    "scale": 3,
    "latitude": 30.74566536567867,
    "longitude": 103.92188101700906,
    "userLatitude": 30.74566536567867,
    "userLongitude": 103.92188101700906,
}

PROXIES = {"http": None, "https": None}


# ══════════════════════════════════════════════════════════
#  后台查询线程（POST + JSON body）
# ══════════════════════════════════════════════════════════
class FetchWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            resp = requests.post(
                NEAR_STATION_URL,
                headers=HEADERS,
                json=PAYLOAD,
                timeout=10,
                proxies=PROXIES,
            )
            if resp.status_code != 200:
                self.error.emit(f"HTTP {resp.status_code}：{resp.text[:200]}")
                return

            raw = resp.json()
            stations = raw["data"]["elecStationData"]
            self.done.emit(stations)
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════
#  颜色 & 样式
# ══════════════════════════════════════════════════════════
def ac(color: QColor, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, alpha)))
    return c

C_BG    = QColor(15, 15, 17)
C_PANEL = QColor(22, 22, 24)
C_SEP   = QColor(50, 50, 55)
C_WHITE = QColor(255, 255, 255)
C_GREY  = QColor(120, 120, 125)
C_GREEN = QColor(48, 209, 88)
C_RED   = QColor(255, 69, 58)
C_BLUE  = QColor(10, 132, 255)

BTN_PRIMARY = """
    QPushButton {
        background: rgba(10,132,255,0.85);
        border: none; border-radius: 8px;
        color: white; font-size: 13px; font-weight: 600;
        padding: 8px 20px;
    }
    QPushButton:hover   { background: rgba(10,132,255,1.0); }
    QPushButton:pressed { background: rgba(0,100,210,1.0); }
    QPushButton:disabled { background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.3); }
"""
BTN_SUCCESS = """
    QPushButton {
        background: rgba(48,209,88,0.85);
        border: none; border-radius: 8px;
        color: white; font-size: 13px; font-weight: 600;
        padding: 8px 20px;
    }
    QPushButton:hover   { background: rgba(48,209,88,1.0); }
    QPushButton:pressed { background: rgba(30,170,60,1.0); }
    QPushButton:disabled { background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.3); }
"""
BTN_GHOST = """
    QPushButton {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.13);
        border-radius: 8px; color: rgba(255,255,255,0.75);
        font-size: 13px; padding: 8px 16px;
    }
    QPushButton:hover   { background: rgba(255,255,255,0.12); }
    QPushButton:pressed { background: rgba(255,255,255,0.05); }
"""
TABLE_STYLE = """
    QTableWidget {
        background: transparent; border: none;
        gridline-color: rgba(255,255,255,0.06);
        color: rgba(255,255,255,0.88); font-size: 13px; outline: none;
    }
    QTableWidget::item { padding: 10px 8px; border: none; }
    QTableWidget::item:selected { background: rgba(10,132,255,0.18); color: white; }
    QHeaderView::section {
        background: rgba(255,255,255,0.05);
        color: rgba(255,255,255,0.45);
        font-size: 11px; font-weight: 600;
        padding: 8px; border: none;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    QScrollBar:vertical { width: 4px; background: transparent; }
    QScrollBar::handle:vertical {
        background: rgba(255,255,255,0.18);
        border-radius: 2px; min-height: 20px;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical { height: 0; }
"""

TOOLTIP_STYLE = """
    QToolTip {
        background: #1c1c1e;
        color: rgba(255,255,255,0.90);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 7px;
        padding: 6px 10px;
        font-size: 12px;
    }
"""


# ══════════════════════════════════════════════════════════
#  空闲数 badge
# ══════════════════════════════════════════════════════════
class FreeNumWidget(QWidget):
    def __init__(self, free_num: int, parent=None):
        super().__init__(parent)
        self.n = free_num
        self.setFixedHeight(36)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        sc  = C_GREEN if self.n > 0 else C_RED
        txt = f"  {self.n} 空闲  " if self.n > 0 else "  全满  "
        p.setFont(QFont("Arial", 11, QFont.Bold))
        fm  = p.fontMetrics()
        bw  = fm.horizontalAdvance(txt) + 8
        bh  = 22
        bx  = (w - bw) // 2
        by  = (h - bh) // 2
        path = QPainterPath()
        path.addRoundedRect(bx, by, bw, bh, bh / 2, bh / 2)
        p.fillPath(path, ac(sc, 35))
        p.setPen(ac(sc, 230))
        p.drawText(int(bx), int(by), int(bw), int(bh), Qt.AlignCenter, txt)


# ══════════════════════════════════════════════════════════
#  主窗口
# ══════════════════════════════════════════════════════════
class StationPicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("充电站查询工具  —  导出 station.json")
        self.setMinimumSize(720, 560)
        self.resize(800, 640)
        self.setStyleSheet(
            f"background: rgb({C_BG.red()},{C_BG.green()},{C_BG.blue()});"
        )

        self._stations: list[dict] = []      # 全量数据（API返回）
        self._stations_shown: list[dict] = [] # 当前显示的数据（过滤后）
        self._worker: FetchWorker | None = None
        self._checks: list[QCheckBox] = []

        self._build_ui()

        # 启动即查询
        self._do_search()

    # ──────────────────────────────────────────────────────
    #  UI 构建
    # ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        # ── 标题区 ────────────────────────────────────────
        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)

        title = QLabel("⚡  充电站查询工具")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color: white;")

        sub = QLabel(
            f"查询范围：{PAYLOAD['latitude']:.4f}, {PAYLOAD['longitude']:.4f}  "
            f"· 半径 scale={PAYLOAD['scale']}  · 最多 {PAYLOAD['pageSize']} 条"
        )
        sub.setFont(QFont("Arial", 11))
        sub.setStyleSheet("color: rgba(255,255,255,0.38);")

        title_col.addWidget(title)
        title_col.addWidget(sub)

        self._refresh_btn = QPushButton("↻  刷新")
        self._refresh_btn.setStyleSheet(BTN_PRIMARY)
        self._refresh_btn.setFixedHeight(36)
        self._refresh_btn.clicked.connect(self._do_search)

        title_row.addLayout(title_col)
        title_row.addStretch()
        title_row.addWidget(self._refresh_btn, 0, Qt.AlignVCenter)
        root.addLayout(title_row)

        # ── 状态栏 ────────────────────────────────────────
        self._status_lbl = QLabel("正在查询…")
        self._status_lbl.setFont(QFont("Arial", 11))
        self._status_lbl.setStyleSheet("color: rgba(255,255,255,0.38);")
        root.addWidget(self._status_lbl)

        # ── 分隔线 ────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(sep)

        # ── 表格工具栏 ────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._select_all_btn = QPushButton("全选")
        self._select_all_btn.setStyleSheet(BTN_GHOST)
        self._select_all_btn.setFixedHeight(32)
        self._select_all_btn.clicked.connect(self._select_all)
        self._select_all_btn.setEnabled(False)

        self._deselect_btn = QPushButton("取消全选")
        self._deselect_btn.setStyleSheet(BTN_GHOST)
        self._deselect_btn.setFixedHeight(32)
        self._deselect_btn.clicked.connect(self._deselect_all)
        self._deselect_btn.setEnabled(False)

        # 搜索框
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍  搜索站点名称或地址…")
        self._search_box.setFixedHeight(32)
        self._search_box.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 8px;
                color: rgba(255,255,255,0.88);
                font-size: 12px;
                padding: 0 10px;
                selection-background-color: rgba(10,132,255,0.5);
            }
            QLineEdit:focus {
                border: 1px solid rgba(10,132,255,0.65);
                background: rgba(255,255,255,0.10);
            }
        """)
        self._search_box.textChanged.connect(self._on_search)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 12px;")

        bar.addWidget(self._select_all_btn)
        bar.addWidget(self._deselect_btn)
        bar.addSpacing(6)
        bar.addWidget(self._search_box, 1)
        bar.addWidget(self._count_lbl)
        root.addLayout(bar)

        # ── 表格 ──────────────────────────────────────────
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["", "站点名称", "站点 ID", "空闲插座", "地址"]
        )
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(3, 110)
        self._table.verticalHeader().setDefaultSectionSize(44)

        root.addWidget(self._table, 1)

        # ── 底部操作栏 ────────────────────────────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(sep2)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self._selected_lbl = QLabel("已选 0 个站点")
        self._selected_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.45); font-size: 12px;"
        )

        self._export_btn = QPushButton("💾  导出 station.json")
        self._export_btn.setStyleSheet(BTN_SUCCESS)
        self._export_btn.setFixedHeight(40)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._do_export)

        bottom.addWidget(self._selected_lbl)
        bottom.addStretch()
        bottom.addWidget(self._export_btn)
        root.addLayout(bottom)

    # ──────────────────────────────────────────────────────
    #  查询
    # ──────────────────────────────────────────────────────
    def _do_search(self):
        if self._worker and self._worker.isRunning():
            return

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("查询中…")
        self._set_status("正在查询附近站点…", error=False)
        self._table.setRowCount(0)
        self._checks.clear()
        self._search_box.blockSignals(True)
        self._search_box.clear()
        self._search_box.blockSignals(False)
        self._select_all_btn.setEnabled(False)
        self._deselect_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._update_counts()

        self._worker = FetchWorker()
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, stations: list):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("↻  刷新")
        self._stations = stations
        self._stations_shown = stations

        if not stations:
            self._set_status("未找到附近站点", error=True)
            return

        self._set_status(f"找到 {len(stations)} 个站点", error=False)
        self._count_lbl.setText(f"共 {len(stations)} 个")
        self._populate_table(stations)
        self._search_box.setEnabled(True)
        self._select_all_btn.setEnabled(True)
        self._deselect_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("↻  刷新")
        self._set_status(f"⚠  请求失败：{msg}", error=True)

    # ──────────────────────────────────────────────────────
    #  实时搜索过滤
    # ──────────────────────────────────────────────────────
    def _on_search(self, text: str):
        kw = text.strip().lower()
        if kw:
            filtered = [
                s for s in self._stations
                if kw in s.get("stationName", "").lower()
                or kw in s.get("address", "").lower()
            ]
        else:
            filtered = list(self._stations)
        self._stations_shown = filtered
        total = len(self._stations)
        shown = len(filtered)
        if kw:
            self._count_lbl.setText(f"{shown} / {total} 个")
        else:
            self._count_lbl.setText(f"共 {total} 个")
        self._populate_table(filtered)

    # ──────────────────────────────────────────────────────
    #  填充表格
    # ──────────────────────────────────────────────────────
    def _populate_table(self, stations: list):
        self._table.setRowCount(0)
        self._checks.clear()

        for row, s in enumerate(stations):
            self._table.insertRow(row)

            # 勾选框
            cb = QCheckBox()
            cb.setChecked(True)
            cb.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px; height: 18px;
                    border-radius: 5px;
                    border: 1.5px solid rgba(255,255,255,0.28);
                    background: rgba(255,255,255,0.06);
                }
                QCheckBox::indicator:checked {
                    background: rgba(10,132,255,0.9);
                    border: 1.5px solid rgba(10,132,255,1.0);
                }
                QCheckBox::indicator:hover {
                    border: 1.5px solid rgba(10,132,255,0.6);
                }
            """)
            cb.stateChanged.connect(self._update_counts)
            cell = QWidget()
            cell_l = QHBoxLayout(cell)
            cell_l.setContentsMargins(0, 0, 0, 0)
            cell_l.setAlignment(Qt.AlignCenter)
            cell_l.addWidget(cb)
            self._table.setCellWidget(row, 0, cell)
            self._checks.append(cb)

            # 站点名
            name = s.get("stationName", "—")
            ni = QTableWidgetItem(name)
            ni.setForeground(C_WHITE)
            ni.setFont(QFont("Arial", 12, QFont.Medium))
            ni.setToolTip(name)
            self._table.setItem(row, 1, ni)

            # 站点 ID
            si = QTableWidgetItem(str(s.get("stationId", "?")))
            si.setForeground(ac(C_GREY, 200))
            si.setTextAlignment(Qt.AlignCenter)
            si.setFont(QFont("Arial", 11))
            self._table.setItem(row, 2, si)

            # 空闲数
            self._table.setCellWidget(row, 3, FreeNumWidget(s.get("freeNum", 0)))

            # 地址
            addr = s.get("address", "—")
            ai = QTableWidgetItem(addr)
            ai.setForeground(ac(C_GREY, 160))
            ai.setFont(QFont("Arial", 11))
            ai.setToolTip(addr)
            self._table.setItem(row, 4, ai)

        self._update_counts()

    # ──────────────────────────────────────────────────────
    #  全选 / 取消全选
    # ──────────────────────────────────────────────────────
    def _select_all(self):
        for cb in self._checks:
            cb.setChecked(True)

    def _deselect_all(self):
        for cb in self._checks:
            cb.setChecked(False)

    def _update_counts(self):
        n = sum(1 for cb in self._checks if cb.isChecked())
        self._selected_lbl.setText(f"已选 {n} 个站点")
        self._export_btn.setEnabled(n > 0)

    # ──────────────────────────────────────────────────────
    #  导出
    # ──────────────────────────────────────────────────────
    def _do_export(self):
        selected = {}
        for cb, s in zip(self._checks, self._stations_shown):
            if cb.isChecked():
                name = s.get("stationName", f"站点{s.get('stationId')}")
                selected[name] = s.get("stationId")

        if not selected:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "保存 station.json", "station.json", "JSON 文件 (*.json)"
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            json.dump(selected, f, ensure_ascii=False, indent=4)

        QMessageBox.information(
            self, "导出成功",
            f"已导出 {len(selected)} 个站点：\n{path}\n\n"
            "将此文件放在监控程序同目录下即可使用。"
        )
        self._set_status(f"✓ 已导出 {len(selected)} 个站点", error=False)

    # ──────────────────────────────────────────────────────
    #  状态提示
    # ──────────────────────────────────────────────────────
    def _set_status(self, msg: str, error: bool = False):
        color = "rgba(255,69,58,0.9)" if error else "rgba(255,255,255,0.38)"
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._status_lbl.setText(msg)

    def paintEvent(self, _):
        QPainter(self).fillRect(self.rect(), C_BG)


# ══════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app.setStyleSheet(TOOLTIP_STYLE)
    win = StationPicker()
    win.show()
    sys.exit(app.exec_())
