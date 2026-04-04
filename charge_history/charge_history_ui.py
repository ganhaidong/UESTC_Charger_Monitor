"""
充电桩历史查询前端。
"""

from __future__ import annotations

import json
import sys
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PyQt5.QtCore import Qt, QThread, QTimer, QSize, QRectF, QSignalBlocker, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


DEFAULT_SERVER_URL = "https://wgooold.cn:8765"
REFRESH_INTERVAL_MS = 30_000


def ac(color: QColor, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, alpha)))
    return c


C_BG_TOP = QColor(7, 10, 14)
C_BG_BOTTOM = QColor(18, 22, 28)
C_CARD = QColor(24, 24, 26)
C_CARD_HI = QColor(33, 35, 40)
C_BORDER = QColor(255, 255, 255, 32)
C_TEXT = QColor(246, 246, 248)
C_MUTED = QColor(137, 141, 148)
C_GREEN = QColor(48, 209, 88)
C_RED = QColor(255, 69, 58)
C_YELLOW = QColor(255, 214, 10)
C_BLUE = QColor(10, 132, 255)


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return app_dir() / "charge_history_ui_config.json"


def load_config() -> Dict[str, Any]:
    return {"server_url": DEFAULT_SERVER_URL}


def save_config(data: Dict[str, Any]) -> None:
    return


def parse_time(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone()


def format_time(value: Optional[str]) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return "-"
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def format_money(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"¥{value:.2f}"


def format_duration(value: Optional[int]) -> str:
    if value is None:
        return "-"
    mins = max(0, int(value))
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}h {mins:02d}m"
    return f"{mins} min"


def status_color(result: str, abnormal: bool = False, in_progress: bool = False) -> QColor:
    if in_progress or result == "in_progress":
        return C_BLUE
    if abnormal or result == "abnormal":
        return C_RED
    return C_GREEN


def status_stylesheet(color: QColor) -> str:
    rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, 0.18)"
    border = f"rgba({color.red()}, {color.green()}, {color.blue()}, 0.80)"
    text = f"rgb({color.red()}, {color.green()}, {color.blue()})"
    return (
        "QLabel {"
        f"background: {rgba};"
        f"border: 1px solid {border};"
        "border-radius: 12px;"
        f"color: {text};"
        "padding: 4px 10px;"
        "font-size: 12px;"
        "font-weight: 700;"
        "}"
    )


class GlassCard(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect().adjusted(0, 0, -1, -1))
        path = QPainterPath()
        path.addRoundedRect(rect, 22, 22)
        painter.fillPath(path, C_CARD)
        gloss = QLinearGradient(0, 0, 0, 70)
        gloss.setColorAt(0.0, ac(C_TEXT, 18))
        gloss.setColorAt(1.0, ac(C_TEXT, 0))
        painter.fillPath(path, gloss)
        painter.setPen(QPen(ac(C_BORDER, 180), 1))
        painter.drawPath(path)


class BadgeLabel(QLabel):
    def set_badge(self, text: str, color: QColor) -> None:
        self.setText(text)
        self.setStyleSheet(status_stylesheet(color))


class PowerTrendWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._points: List[Dict[str, Any]] = []
        self._status_text = "未选择会话"
        self._line_color = C_BLUE
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_session(self, session: Optional[Dict[str, Any]]) -> None:
        if not session:
            self._points = []
            self._status_text = "未选择会话"
            self._line_color = C_BLUE
            self.update()
            return
        self._points = list(session.get("points", []))
        self._status_text = session.get("status_text", "会话详情")
        self._line_color = status_color(
            session.get("result", ""),
            bool(session.get("abnormal")),
            bool(session.get("is_in_progress")),
        )
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect().adjusted(0, 0, -1, -1))
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        painter.fillPath(path, QColor(16, 18, 22))
        painter.setPen(QPen(ac(C_BORDER, 180), 1))
        painter.drawPath(path)

        title_rect = rect.adjusted(16, 12, -16, -12)
        painter.setPen(self._line_color)
        painter.setFont(QFont("Bahnschrift SemiBold", 11))
        painter.drawText(title_rect.adjusted(0, 0, 0, -title_rect.height() + 20), Qt.AlignLeft, self._status_text)

        if len(self._points) < 2:
            painter.setPen(ac(C_MUTED, 210))
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            painter.drawText(rect.adjusted(16, 40, -16, -16), Qt.AlignCenter, "分钟级采样明细会在这里显示功率走势")
            return

        plot = rect.adjusted(18, 42, -18, -18)
        powers = [pt["power_w"] for pt in self._points if pt.get("power_w") is not None]
        if len(powers) < 2:
            painter.setPen(ac(C_MUTED, 210))
            painter.drawText(plot, Qt.AlignCenter, "当前会话没有有效功率点")
            return

        max_power = max(max(powers), 100)
        min_power = min(min(powers), 0)
        span = max(1.0, float(max_power - min_power))

        timeline = []
        base_time = parse_time(self._points[0].get("sample_time"))
        for point in self._points:
            ts = parse_time(point.get("sample_time"))
            power = point.get("power_w")
            if ts is None or power is None:
                continue
            timeline.append((ts, power))
        if len(timeline) < 2:
            painter.setPen(ac(C_MUTED, 210))
            painter.drawText(plot, Qt.AlignCenter, "当前会话没有有效时间点")
            return

        total_seconds = max(1.0, (timeline[-1][0] - timeline[0][0]).total_seconds())

        def tx(ts: dt.datetime) -> float:
            return plot.left() + ((ts - timeline[0][0]).total_seconds() / total_seconds) * plot.width()

        def ty(power: int) -> float:
            return plot.bottom() - ((power - min_power) / span) * plot.height()

        painter.setPen(QPen(ac(C_TEXT, 20), 1))
        for step in range(4):
            y = plot.top() + plot.height() * step / 3.0
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))

        area = QPainterPath()
        line = QPainterPath()
        first_x = tx(timeline[0][0])
        first_y = ty(timeline[0][1])
        line.moveTo(first_x, first_y)
        area.moveTo(first_x, plot.bottom())
        area.lineTo(first_x, first_y)
        for ts, power in timeline[1:]:
            x = tx(ts)
            y = ty(power)
            line.lineTo(x, y)
            area.lineTo(x, y)
        area.lineTo(tx(timeline[-1][0]), plot.bottom())
        area.closeSubpath()

        fill = QLinearGradient(0, plot.top(), 0, plot.bottom())
        fill.setColorAt(0.0, ac(self._line_color, 80))
        fill.setColorAt(1.0, ac(self._line_color, 8))
        painter.fillPath(area, fill)
        painter.setPen(QPen(self._line_color, 2.2))
        painter.drawPath(line)

        painter.setPen(ac(C_MUTED, 220))
        painter.setFont(QFont("Bahnschrift", 9))
        painter.drawText(plot.adjusted(0, 4, 0, 0), Qt.AlignLeft | Qt.AlignTop, f"{max_power}W")
        painter.drawText(plot.adjusted(0, 0, 0, -4), Qt.AlignRight | Qt.AlignBottom, timeline[-1][0].strftime("%H:%M"))
        painter.drawText(plot.adjusted(0, 0, 0, -4), Qt.AlignLeft | Qt.AlignBottom, timeline[0][0].strftime("%H:%M"))


class HistoryApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error") or "接口返回失败")
        return payload.get("data")

    def health(self) -> Dict[str, Any]:
        return self._get("/api/health")

    def stations(self) -> List[Dict[str, Any]]:
        return self._get("/api/stations")

    def outlets(self, station_id: int, search: str = "") -> List[Dict[str, Any]]:
        return self._get("/api/outlets", {"station_id": station_id, "search": search})

    def sessions(self, station_id: int, outlet_no: str, days: int) -> List[Dict[str, Any]]:
        return self._get("/api/sessions", {"station_id": station_id, "outlet_no": outlet_no, "days": days})

    def session_detail(self, session_id: int) -> Dict[str, Any]:
        return self._get("/api/session", {"session_id": session_id})

    def collect(self) -> Dict[str, Any]:
        return self._get("/api/admin/collect", timeout=120)


class ApiWorker(QThread):
    finished = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(self, action: str, base_url: str, params: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.action = action
        self.base_url = base_url
        self.params = params or {}

    def run(self) -> None:
        client = HistoryApiClient(self.base_url)
        try:
            if self.action == "health":
                payload = client.health()
            elif self.action == "bootstrap":
                payload = {
                    "health": client.health(),
                    "stations": client.stations(),
                }
            elif self.action == "outlets":
                payload = {
                    "station_id": self.params["station_id"],
                    "items": client.outlets(self.params["station_id"], self.params.get("search", "")),
                }
            elif self.action == "sessions":
                payload = {
                    "station_id": self.params["station_id"],
                    "outlet_no": self.params["outlet_no"],
                    "items": client.sessions(
                        self.params["station_id"],
                        self.params["outlet_no"],
                        self.params["days"],
                    ),
                }
            elif self.action == "session_detail":
                payload = {
                    "session_id": self.params["session_id"],
                    "item": client.session_detail(self.params["session_id"]),
                }
            elif self.action == "collect":
                payload = client.collect()
            else:
                raise RuntimeError(f"未知操作: {self.action}")
            self.finished.emit(self.action, payload)
        except Exception as exc:
            self.failed.emit(self.action, str(exc))


class HistoryWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._config = load_config()
        self._base_url = self._config["server_url"]
        self._workers: List[ApiWorker] = []
        self._busy_actions: set[str] = set()
        self._health: Dict[str, Any] = {}
        self._all_stations: List[Dict[str, Any]] = []
        self._filtered_stations: List[Dict[str, Any]] = []
        self._all_outlets: List[Dict[str, Any]] = []
        self._filtered_outlets: List[Dict[str, Any]] = []
        self._sessions: List[Dict[str, Any]] = []
        self._selected_station: Optional[Dict[str, Any]] = None
        self._selected_outlet: Optional[Dict[str, Any]] = None
        self._selected_session: Optional[Dict[str, Any]] = None
        self._layout_bucket = ""
        self._station_item_height = 58
        self._outlet_item_height = 56

        self.setWindowTitle("充电桩历史库")
        self._set_initial_window_geometry()
        icon_path = resource_dir() / "charge.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_ui()
        self._apply_styles()
        QTimer.singleShot(0, lambda: self._apply_responsive_layout(force=True))

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_context)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

        self.refresh_all()

    def _set_initial_window_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1440, 920)
            self.setMinimumSize(980, 620)
            return

        available = screen.availableGeometry()
        width = min(max(960, int(available.width() * 0.90)), max(available.width() - 24, 760))
        height = min(max(640, int(available.height() * 0.90)), max(available.height() - 48, 560))
        self.resize(width, height)
        self.setMinimumSize(min(width, 900), min(height, 600))

    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(16, 16, 16, 16)
        self.root_layout.setSpacing(10)

        self.header_card = GlassCard(self)
        self.header_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header_layout = QGridLayout(self.header_card)
        self.header_layout.setContentsMargins(14, 14, 14, 14)
        self.header_layout.setHorizontalSpacing(10)
        self.header_layout.setVerticalSpacing(6)

        self.title_label = QLabel("Charging History Console", self.header_card)
        self.title_label.setFont(QFont("Bahnschrift SemiBold", 18))
        self.subtitle_label = QLabel("三天内分钟级采样，按站点和插座回看每一段充电历史", self.header_card)
        self.subtitle_label.setFont(QFont("Microsoft YaHei UI", 9))
        self.subtitle_label.setWordWrap(True)

        self.refresh_btn = QPushButton("刷新数据", self.header_card)
        self.refresh_btn.clicked.connect(self.refresh_all)

        self.status_badge = BadgeLabel(self.header_card)
        self.status_badge.set_badge("等待连接", C_YELLOW)
        self.status_detail = QLabel("尚未获取后端状态", self.header_card)
        self.status_detail.setFont(QFont("Microsoft YaHei UI", 8))
        self.status_detail.setWordWrap(True)
        self.status_detail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.header_layout.addWidget(self.title_label, 0, 0, 1, 2)
        self.header_layout.addWidget(self.subtitle_label, 1, 0, 1, 2)
        self.header_layout.addWidget(self.refresh_btn, 0, 2)
        self.header_layout.addWidget(self.status_badge, 1, 2)
        self.header_layout.addWidget(self.status_detail, 0, 3, 2, 1)
        self.header_layout.setColumnStretch(0, 1)
        self.header_layout.setColumnStretch(1, 1)
        self.header_layout.setColumnStretch(3, 1)
        self.root_layout.addWidget(self.header_card)

        self.main_splitter = QSplitter(Qt.Horizontal, self)
        self.main_splitter.setChildrenCollapsible(False)

        left_panel = QWidget(self.main_splitter)
        self.left_layout = QVBoxLayout(left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)

        self.station_card = GlassCard(left_panel)
        self.station_layout = QVBoxLayout(self.station_card)
        self.station_layout.setContentsMargins(12, 12, 12, 12)
        self.station_layout.setSpacing(8)
        self.station_title = QLabel("站点", self.station_card)
        self.station_title.setFont(QFont("Bahnschrift SemiBold", 9))
        self.station_search = QLineEdit(self.station_card)
        self.station_search.setPlaceholderText("搜索站点名")
        self.station_search.setMaximumHeight(38)
        self.station_search.textChanged.connect(self.apply_station_filter)
        self.station_list = QListWidget(self.station_card)
        self.station_list.itemSelectionChanged.connect(self.on_station_changed)
        self.station_layout.addWidget(self.station_title)
        self.station_layout.addWidget(self.station_search)
        self.station_layout.addWidget(self.station_list, 1)
        self.left_layout.addWidget(self.station_card, 2)

        self.outlet_card = GlassCard(left_panel)
        self.outlet_layout = QVBoxLayout(self.outlet_card)
        self.outlet_layout.setContentsMargins(12, 12, 12, 12)
        self.outlet_layout.setSpacing(8)
        self.outlet_title = QLabel("插座", self.outlet_card)
        self.outlet_title.setFont(QFont("Bahnschrift SemiBold", 9))
        self.outlet_search = QLineEdit(self.outlet_card)
        self.outlet_search.setPlaceholderText("按序号或 outletNo 过滤")
        self.outlet_search.setMaximumHeight(38)
        self.outlet_search.textChanged.connect(self.apply_outlet_filter)
        self.outlet_list = QListWidget(self.outlet_card)
        self.outlet_list.itemSelectionChanged.connect(self.on_outlet_changed)
        self.outlet_layout.addWidget(self.outlet_title)
        self.outlet_layout.addWidget(self.outlet_search)
        self.outlet_layout.addWidget(self.outlet_list, 1)
        self.left_layout.addWidget(self.outlet_card, 3)

        right_panel = QWidget(self.main_splitter)
        self.right_layout = QVBoxLayout(right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(10)

        self.summary_card = GlassCard(right_panel)
        self.summary_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.summary_layout = QGridLayout(self.summary_card)
        self.summary_layout.setContentsMargins(12, 10, 12, 10)
        self.summary_layout.setHorizontalSpacing(10)
        self.summary_layout.setVerticalSpacing(6)
        self.summary_station = QLabel("未选择站点", self.summary_card)
        self.summary_station.setFont(QFont("Bahnschrift SemiBold", 12))
        self.summary_outlet = QLabel("未选择插座", self.summary_card)
        self.summary_outlet.setFont(QFont("Microsoft YaHei UI", 10))
        self.summary_status = BadgeLabel(self.summary_card)
        self.summary_status.set_badge("等待选择", C_YELLOW)
        self.summary_meta = QLabel("请选择左侧站点和插座。", self.summary_card)
        self.summary_meta.setFont(QFont("Microsoft YaHei UI", 9))
        self.summary_meta.setWordWrap(True)
        self.summary_meta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.days_label = QLabel("历史范围", self.summary_card)
        self.days_label.setFont(QFont("Microsoft YaHei UI", 9))
        self.days_spin = QSpinBox(self.summary_card)
        self.days_spin.setRange(1, 3)
        self.days_spin.setValue(3)
        self.days_spin.valueChanged.connect(self.reload_sessions)
        self.summary_layout.addWidget(self.summary_station, 0, 0, 1, 3)
        self.summary_layout.addWidget(self.summary_status, 0, 3)
        self.summary_layout.addWidget(self.summary_outlet, 1, 0, 1, 2)
        self.summary_layout.addWidget(self.days_label, 1, 2, Qt.AlignRight)
        self.summary_layout.addWidget(self.days_spin, 1, 3)
        self.summary_layout.addWidget(self.summary_meta, 2, 0, 1, 4)
        self.summary_layout.setColumnStretch(0, 1)
        self.summary_layout.setColumnStretch(1, 1)
        self.right_layout.addWidget(self.summary_card, 0)

        self.right_content_splitter = QSplitter(Qt.Vertical, right_panel)
        self.right_content_splitter.setChildrenCollapsible(False)

        self.sessions_card = GlassCard(self.right_content_splitter)
        self.sessions_card.setMinimumHeight(180)
        self.sessions_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sessions_layout = QVBoxLayout(self.sessions_card)
        self.sessions_layout.setContentsMargins(12, 10, 12, 12)
        self.sessions_layout.setSpacing(8)
        self.sessions_title = QLabel("充电会话", self.sessions_card)
        self.sessions_title.setFont(QFont("Bahnschrift SemiBold", 9))
        self.session_table = self._create_table(
            ["状态", "开始时间", "结束时间", "时长", "采样点", "最后功率", "最终费用"]
        )
        self.session_table.itemSelectionChanged.connect(self.on_session_changed)
        self.sessions_layout.addWidget(self.sessions_title)
        self.sessions_layout.addWidget(self.session_table, 1)

        self.detail_card = GlassCard(self.right_content_splitter)
        self.detail_card.setMinimumHeight(220)
        self.detail_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.detail_layout = QVBoxLayout(self.detail_card)
        self.detail_layout.setContentsMargins(12, 10, 12, 12)
        self.detail_layout.setSpacing(8)
        detail_head = QHBoxLayout()
        detail_head.setContentsMargins(0, 0, 0, 0)
        self.detail_title = QLabel("会话明细", self.detail_card)
        self.detail_title.setFont(QFont("Bahnschrift SemiBold", 9))
        self.detail_badge = BadgeLabel(self.detail_card)
        self.detail_badge.set_badge("等待选择", C_YELLOW)
        detail_head.addWidget(self.detail_title)
        detail_head.addStretch(1)
        detail_head.addWidget(self.detail_badge)
        self.detail_meta = QLabel("选择一段会话后，这里会展示开始时间、结束时间、分钟级采样明细和功率趋势。", self.detail_card)
        self.detail_meta.setFont(QFont("Microsoft YaHei UI", 9))
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.power_chart = PowerTrendWidget(self.detail_card)
        self.detail_layout.addLayout(detail_head)
        self.detail_layout.addWidget(self.detail_meta)
        self.detail_layout.addWidget(self.power_chart, 1)
        self.right_content_splitter.addWidget(self.sessions_card)
        self.right_content_splitter.addWidget(self.detail_card)
        self.right_content_splitter.setStretchFactor(0, 3)
        self.right_content_splitter.setStretchFactor(1, 5)
        self.right_layout.addWidget(self.right_content_splitter, 1)

        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(right_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.root_layout.addWidget(self.main_splitter, 1)

    def _apply_styles(self) -> None:
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            QWidget {
                color: rgb(246, 246, 248);
                font-family: "Microsoft YaHei UI";
            }
            QLabel {
                background: transparent;
            }
            QLineEdit, QSpinBox {
                background: rgba(6, 7, 10, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 12px;
                selection-background-color: rgba(10, 132, 255, 0.35);
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid rgba(10, 132, 255, 0.8);
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.14);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.18);
            }
            QListWidget, QTableWidget {
                background: rgba(10, 12, 16, 0.80);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                gridline-color: rgba(255, 255, 255, 0.05);
                outline: none;
                padding: 3px;
            }
            QListWidget::item {
                background: transparent;
                border-radius: 12px;
                padding: 6px 8px;
                margin: 2px 1px;
            }
            QListWidget::item:selected {
                background: rgba(10, 132, 255, 0.18);
                border: 1px solid rgba(10, 132, 255, 0.50);
            }
            QHeaderView::section {
                background-color: rgb(22, 26, 33);
                color: rgb(236, 238, 242);
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.10);
                padding: 7px 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            }
            QTableWidget::item:selected {
                background: rgba(10, 132, 255, 0.20);
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 6px 0 6px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.18);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QSplitter::handle {
                background: transparent;
            }
            """
        )

    def _apply_responsive_layout(self, force: bool = False) -> None:
        width = max(self.width(), self.minimumWidth())
        height = max(self.height(), self.minimumHeight())

        if width < 1260 or height < 760:
            bucket = "compact"
            metrics = {
                "margin": 12,
                "spacing": 8,
                "card_padding": 10,
                "panel_spacing": 8,
                "header_height": 100,
                "summary_height": 112,
                "search_height": 34,
                "section_title": 8,
                "title_font": 16,
                "subtitle_font": 8,
                "summary_station_font": 11,
                "summary_text_font": 9,
                "status_detail_font": 8,
                "sessions_min": 180,
                "detail_min": 220,
                "chart_min": 180,
                "station_item": 52,
                "outlet_item": 50,
                "table_header": 30,
                "table_row": 28,
                "left_ratio": 0.28,
                "top_ratio": 0.43,
            }
        elif width < 1600 or height < 940:
            bucket = "regular"
            metrics = {
                "margin": 16,
                "spacing": 10,
                "card_padding": 12,
                "panel_spacing": 10,
                "header_height": 108,
                "summary_height": 118,
                "search_height": 38,
                "section_title": 9,
                "title_font": 18,
                "subtitle_font": 9,
                "summary_station_font": 12,
                "summary_text_font": 10,
                "status_detail_font": 8,
                "sessions_min": 200,
                "detail_min": 250,
                "chart_min": 220,
                "station_item": 58,
                "outlet_item": 56,
                "table_header": 32,
                "table_row": 30,
                "left_ratio": 0.24,
                "top_ratio": 0.41,
            }
        else:
            bucket = "spacious"
            metrics = {
                "margin": 20,
                "spacing": 12,
                "card_padding": 14,
                "panel_spacing": 12,
                "header_height": 118,
                "summary_height": 126,
                "search_height": 40,
                "section_title": 10,
                "title_font": 20,
                "subtitle_font": 10,
                "summary_station_font": 13,
                "summary_text_font": 10,
                "status_detail_font": 9,
                "sessions_min": 230,
                "detail_min": 300,
                "chart_min": 260,
                "station_item": 64,
                "outlet_item": 62,
                "table_header": 34,
                "table_row": 32,
                "left_ratio": 0.22,
                "top_ratio": 0.40,
            }

        self.root_layout.setContentsMargins(
            metrics["margin"], metrics["margin"], metrics["margin"], metrics["margin"]
        )
        self.root_layout.setSpacing(metrics["spacing"])
        self.left_layout.setSpacing(metrics["spacing"])
        self.right_layout.setSpacing(metrics["spacing"])
        self.station_layout.setContentsMargins(
            metrics["card_padding"], metrics["card_padding"], metrics["card_padding"], metrics["card_padding"]
        )
        self.outlet_layout.setContentsMargins(
            metrics["card_padding"], metrics["card_padding"], metrics["card_padding"], metrics["card_padding"]
        )
        self.sessions_layout.setContentsMargins(
            metrics["card_padding"], metrics["card_padding"], metrics["card_padding"], metrics["card_padding"]
        )
        self.detail_layout.setContentsMargins(
            metrics["card_padding"], metrics["card_padding"], metrics["card_padding"], metrics["card_padding"]
        )
        self.summary_layout.setContentsMargins(
            metrics["card_padding"], metrics["card_padding"] - 2, metrics["card_padding"], metrics["card_padding"] - 2
        )

        self.station_layout.setSpacing(metrics["panel_spacing"])
        self.outlet_layout.setSpacing(metrics["panel_spacing"])
        self.sessions_layout.setSpacing(metrics["panel_spacing"])
        self.detail_layout.setSpacing(metrics["panel_spacing"])
        self.header_layout.setHorizontalSpacing(metrics["spacing"])
        self.header_layout.setVerticalSpacing(max(4, metrics["spacing"] - 4))
        self.summary_layout.setHorizontalSpacing(metrics["spacing"])
        self.summary_layout.setVerticalSpacing(max(4, metrics["spacing"] - 4))

        self.header_card.setFixedHeight(metrics["header_height"])
        self.summary_card.setFixedHeight(metrics["summary_height"])
        self.sessions_card.setMinimumHeight(metrics["sessions_min"])
        self.detail_card.setMinimumHeight(metrics["detail_min"])
        self.power_chart.setMinimumHeight(metrics["chart_min"])
        self.station_search.setMaximumHeight(metrics["search_height"])
        self.outlet_search.setMaximumHeight(metrics["search_height"])

        self.title_label.setFont(QFont("Bahnschrift SemiBold", metrics["title_font"]))
        self.subtitle_label.setFont(QFont("Microsoft YaHei UI", metrics["subtitle_font"]))
        self.status_detail.setFont(QFont("Microsoft YaHei UI", metrics["status_detail_font"]))
        self.station_title.setFont(QFont("Bahnschrift SemiBold", metrics["section_title"]))
        self.outlet_title.setFont(QFont("Bahnschrift SemiBold", metrics["section_title"]))
        self.sessions_title.setFont(QFont("Bahnschrift SemiBold", metrics["section_title"]))
        self.detail_title.setFont(QFont("Bahnschrift SemiBold", metrics["section_title"]))
        self.summary_station.setFont(QFont("Bahnschrift SemiBold", metrics["summary_station_font"]))
        self.summary_outlet.setFont(QFont("Microsoft YaHei UI", metrics["summary_text_font"]))
        self.summary_meta.setFont(QFont("Microsoft YaHei UI", max(8, metrics["summary_text_font"] - 1)))
        self.days_label.setFont(QFont("Microsoft YaHei UI", max(8, metrics["summary_text_font"] - 1)))
        self.detail_meta.setFont(QFont("Microsoft YaHei UI", max(8, metrics["summary_text_font"] - 1)))

        header = self.session_table.horizontalHeader()
        header.setFixedHeight(metrics["table_header"])
        self.session_table.verticalHeader().setDefaultSectionSize(metrics["table_row"])

        self._station_item_height = metrics["station_item"]
        self._outlet_item_height = metrics["outlet_item"]

        if force or bucket != self._layout_bucket:
            content_width = max(820, width - (metrics["margin"] * 2))
            left_width = max(220, min(360, int(content_width * metrics["left_ratio"])))
            right_width = max(540, content_width - left_width)
            self.main_splitter.setSizes([left_width, right_width])

            available_height = max(
                metrics["sessions_min"] + metrics["detail_min"],
                height - metrics["header_height"] - metrics["summary_height"] - (metrics["margin"] * 2) - (metrics["spacing"] * 2),
            )
            top_height = max(metrics["sessions_min"], int(available_height * metrics["top_ratio"]))
            bottom_height = max(metrics["detail_min"], available_height - top_height)
            self.right_content_splitter.setSizes([top_height, bottom_height])

        self._layout_bucket = bucket

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "main_splitter"):
            self._apply_responsive_layout()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, C_BG_TOP)
        gradient.setColorAt(1.0, C_BG_BOTTOM)
        painter.fillRect(self.rect(), gradient)

        painter.setPen(Qt.NoPen)
        painter.setBrush(ac(C_BLUE, 18))
        painter.drawEllipse(int(self.width() * 0.68), -100, 360, 260)
        painter.setBrush(ac(C_GREEN, 12))
        painter.drawEllipse(-120, int(self.height() * 0.65), 300, 220)

    def _create_table(self, headers: List[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers), self)
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.setWordWrap(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setFixedHeight(32)
        header.setStyleSheet(
            """
            QHeaderView::section {
                background-color: rgb(22, 26, 33);
                color: rgb(236, 238, 242);
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.10);
                border-right: 1px solid rgba(255, 255, 255, 0.05);
                padding: 7px 6px;
                font-size: 11px;
                font-weight: 700;
            }
            """
        )
        table.verticalHeader().setDefaultSectionSize(30)
        return table

    def _set_status(self, text: str, color: QColor, detail: str) -> None:
        self.status_badge.set_badge(text, color)
        self.status_detail.setText(detail)

    def _start_worker(self, action: str, params: Optional[Dict[str, Any]] = None) -> None:
        if action in self._busy_actions:
            return
        self._busy_actions.add(action)
        worker = ApiWorker(action, self._base_url, params)
        worker.finished.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda _a, _d, w=worker: self._release_worker(w))
        worker.failed.connect(lambda _a, _e, w=worker: self._release_worker(w))
        self._workers.append(worker)
        worker.start()

    def _release_worker(self, worker: ApiWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        self._busy_actions.discard(worker.action)
        worker.deleteLater()

    def refresh_all(self) -> None:
        self._set_status("正在连接", C_BLUE, f"正在访问 {self._base_url}")
        self._start_worker("bootstrap")

    def refresh_context(self) -> None:
        self._start_worker("health")
        if self._selected_station:
            self._start_worker("outlets", {"station_id": self._selected_station["station_id"], "search": ""})
        if self._selected_station and self._selected_outlet:
            self._start_worker(
                "sessions",
                {
                    "station_id": self._selected_station["station_id"],
                    "outlet_no": self._selected_outlet["outlet_no"],
                    "days": self.days_spin.value(),
                },
            )
        if self._selected_session:
            self._start_worker("session_detail", {"session_id": self._selected_session["id"]})

    def apply_station_filter(self) -> None:
        keyword = self.station_search.text().strip().lower()
        if keyword:
            self._filtered_stations = [
                item for item in self._all_stations
                if keyword in item.get("station_name", "").lower()
            ]
        else:
            self._filtered_stations = list(self._all_stations)
        self._render_station_list()

    def apply_outlet_filter(self) -> None:
        keyword = self.outlet_search.text().strip().lower()
        if keyword:
            self._filtered_outlets = [
                item for item in self._all_outlets
                if keyword in str(item.get("serial", "")).lower()
                or keyword in item.get("outlet_no", "").lower()
            ]
        else:
            self._filtered_outlets = list(self._all_outlets)
        self._render_outlet_list()

    def on_station_changed(self) -> None:
        item = self.station_list.currentItem()
        self._selected_station = item.data(Qt.UserRole) if item else None
        self._selected_outlet = None
        self._selected_session = None
        self._all_outlets = []
        self._filtered_outlets = []
        self._sessions = []
        self._render_outlet_list()
        self._render_sessions([])
        self._render_session_detail(None)
        self._update_summary()
        if self._selected_station:
            self._start_worker("outlets", {"station_id": self._selected_station["station_id"], "search": ""})

    def on_outlet_changed(self) -> None:
        item = self.outlet_list.currentItem()
        self._selected_outlet = item.data(Qt.UserRole) if item else None
        self._selected_session = None
        self._render_sessions([])
        self._render_session_detail(None)
        self._update_summary()
        self.reload_sessions()

    def reload_sessions(self) -> None:
        if not self._selected_station or not self._selected_outlet:
            return
        self._start_worker(
            "sessions",
            {
                "station_id": self._selected_station["station_id"],
                "outlet_no": self._selected_outlet["outlet_no"],
                "days": self.days_spin.value(),
            },
        )

    def on_session_changed(self) -> None:
        items = self.session_table.selectedItems()
        if not items:
            self._selected_session = None
            self._render_session_detail(None)
            return
        row = items[0].row()
        first_item = self.session_table.item(row, 0)
        if first_item is None:
            return
        session = first_item.data(Qt.UserRole)
        self._selected_session = session
        if session:
            self._start_worker("session_detail", {"session_id": session["id"]})

    def _on_worker_finished(self, action: str, payload: Any) -> None:
        if action == "health":
            self._health = payload
            self._set_health_status()
            return

        if action == "bootstrap":
            previous_station_id = self._selected_station.get("station_id") if self._selected_station else None
            self._health = payload["health"]
            self._all_stations = payload["stations"]
            self.apply_station_filter()
            self._sync_selected_station(emit_change=previous_station_id is None)
            self._set_health_status()
            if previous_station_id is not None and self._selected_station:
                self.refresh_context()
            return

        if action == "outlets":
            if not self._selected_station or payload["station_id"] != self._selected_station["station_id"]:
                return
            had_selection = self._selected_outlet is not None
            self._all_outlets = payload["items"]
            self.apply_outlet_filter()
            self._sync_selected_outlet(emit_change=not had_selection)
            return

        if action == "sessions":
            if not self._selected_outlet or payload["outlet_no"] != self._selected_outlet["outlet_no"]:
                return
            had_selection = self._selected_session is not None
            self._sessions = payload["items"]
            self._render_sessions(self._sessions)
            self._sync_selected_session(emit_change=not had_selection)
            return

        if action == "session_detail":
            if self._selected_session and payload["session_id"] != self._selected_session["id"]:
                return
            self._selected_session = payload["item"]
            self._render_session_detail(self._selected_session)
            return

    def _on_worker_failed(self, action: str, error: str) -> None:
        self._set_status("连接失败", C_RED, error)

    def _set_health_status(self) -> None:
        collector = self._health.get("collector", {})
        totals = self._health.get("totals", {})
        if collector.get("is_collecting"):
            self._set_status("采集中", C_BLUE, "后端正在执行分钟级采样。")
            return
        last_finish = collector.get("last_run_finished_at")
        detail = (
            f"站点 {totals.get('station_count', 0)} 个，插座 {totals.get('outlet_count', 0)} 个，"
            f"进行中 {totals.get('active_sessions', 0)} 段，最近完成：{format_time(last_finish)}"
        )
        self._set_status("在线", C_GREEN, detail)

    def _render_station_list(self) -> None:
        scroll = self.station_list.verticalScrollBar().value()
        with QSignalBlocker(self.station_list):
            self.station_list.clear()
            for station in self._filtered_stations:
                text = (
                    f"{station['station_name']}\n"
                    f"{station.get('outlet_count', 0)} 个插座 · {station.get('busy_count', 0)} 占用 · "
                    f"{station.get('in_progress_count', 0)} 段进行中"
                )
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, station)
                item.setSizeHint(QSize(0, self._station_item_height))
                self.station_list.addItem(item)
        self.station_list.verticalScrollBar().setValue(scroll)

    def _render_outlet_list(self) -> None:
        scroll = self.outlet_list.verticalScrollBar().value()
        with QSignalBlocker(self.outlet_list):
            self.outlet_list.clear()
            for outlet in self._filtered_outlets:
                first = f"插座 {int(outlet.get('serial', 0)):02d}"
                second = outlet.get("status_text", "未知")
                if outlet.get("is_in_progress"):
                    second = "正在充电"
                if outlet.get("current_power_w") is not None:
                    second += f" · {outlet['current_power_w']}W"
                if outlet.get("current_fee") is not None:
                    second += f" · {format_money(outlet['current_fee'])}"
                item = QListWidgetItem(f"{first}\n{second}")
                item.setData(Qt.UserRole, outlet)
                item.setSizeHint(QSize(0, self._outlet_item_height))
                self.outlet_list.addItem(item)
        self.outlet_list.verticalScrollBar().setValue(scroll)

    def _render_sessions(self, sessions: List[Dict[str, Any]]) -> None:
        scroll = self.session_table.verticalScrollBar().value()
        with QSignalBlocker(self.session_table):
            self.session_table.setRowCount(len(sessions))
            for row, session in enumerate(sessions):
                color = status_color(
                    session.get("result", ""),
                    bool(session.get("abnormal")),
                    bool(session.get("is_in_progress")),
                )
                values = [
                    session.get("status_text", "-"),
                    format_time(session.get("start_time")),
                    "正在充电" if session.get("is_in_progress") else format_time(session.get("end_time")),
                    format_duration(session.get("duration_min")),
                    str(session.get("sample_count", 0)),
                    "-" if session.get("last_power_w") is None else f"{session['last_power_w']}W",
                    format_money(session.get("final_fee")),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        item.setForeground(color)
                        item.setData(Qt.UserRole, session)
                    self.session_table.setItem(row, col, item)
        self.session_table.resizeRowsToContents()
        self.session_table.verticalScrollBar().setValue(scroll)

    def _render_session_detail(self, session: Optional[Dict[str, Any]]) -> None:
        if not session:
            self.detail_badge.set_badge("等待选择", C_YELLOW)
            self.detail_meta.setText("选择一段会话后，这里会展示开始时间、结束时间、分钟级采样明细和功率趋势。")
            self.power_chart.set_session(None)
            return

        color = status_color(
            session.get("result", ""),
            bool(session.get("abnormal")),
            bool(session.get("is_in_progress")),
        )
        self.detail_badge.set_badge(session.get("status_text", "会话"), color)
        self.detail_meta.setText(
            "开始：{start}    结束：{end}    时长：{duration}    采样点：{count}    基线功率：{baseline}".format(
                start=format_time(session.get("start_time")),
                end="正在充电" if session.get("is_in_progress") else format_time(session.get("end_time")),
                duration=format_duration(session.get("duration_min")),
                count=session.get("sample_count", 0),
                baseline="-"
                if session.get("baseline_power_w") is None
                else f"{session['baseline_power_w']}W",
            )
        )
        self.power_chart.set_session(session)

    def _sync_selected_station(self, emit_change: bool = True) -> None:
        current_id = self._selected_station.get("station_id") if self._selected_station else None
        target_row = None
        for row, station in enumerate(self._filtered_stations):
            if current_id is not None and station["station_id"] == current_id:
                target_row = row
                break
        if self._filtered_stations:
            if target_row is None:
                target_row = 0
            if emit_change:
                self.station_list.setCurrentRow(target_row)
            else:
                with QSignalBlocker(self.station_list):
                    self.station_list.setCurrentRow(target_row)
                item = self.station_list.item(target_row)
                self._selected_station = item.data(Qt.UserRole) if item else None
        else:
            self._selected_station = None

    def _sync_selected_outlet(self, emit_change: bool = True) -> None:
        current_outlet = self._selected_outlet.get("outlet_no") if self._selected_outlet else None
        target_row = None
        for row, outlet in enumerate(self._filtered_outlets):
            if current_outlet and outlet["outlet_no"] == current_outlet:
                target_row = row
                break
        if self._filtered_outlets:
            if target_row is None and emit_change:
                target_row = 0
            if target_row is not None:
                if emit_change:
                    self.outlet_list.setCurrentRow(target_row)
                else:
                    with QSignalBlocker(self.outlet_list):
                        self.outlet_list.setCurrentRow(target_row)
                    item = self.outlet_list.item(target_row)
                    self._selected_outlet = item.data(Qt.UserRole) if item else None
                    self._update_summary()
            else:
                with QSignalBlocker(self.outlet_list):
                    self.outlet_list.clearSelection()
                self._selected_outlet = None
                self._update_summary()
        else:
            self._selected_outlet = None
            self._update_summary()

    def _sync_selected_session(self, emit_change: bool = True) -> None:
        current_session_id = self._selected_session.get("id") if self._selected_session else None
        if not self._sessions:
            self._selected_session = None
            self._render_session_detail(None)
            return
        target_row = None
        for row, session in enumerate(self._sessions):
            if current_session_id is not None and session["id"] == current_session_id:
                target_row = row
                break
        if target_row is None and emit_change:
            target_row = 0
        if target_row is not None:
            if emit_change:
                self.session_table.setCurrentCell(target_row, 0)
            else:
                with QSignalBlocker(self.session_table):
                    self.session_table.setCurrentCell(target_row, 0)
                first_item = self.session_table.item(target_row, 0)
                self._selected_session = first_item.data(Qt.UserRole) if first_item else None
        else:
            with QSignalBlocker(self.session_table):
                self.session_table.clearSelection()
            self._selected_session = None
        self._update_summary()

    def _update_summary(self) -> None:
        station_name = self._selected_station.get("station_name") if self._selected_station else "未选择站点"
        self.summary_station.setText(station_name)
        if not self._selected_outlet:
            self.summary_outlet.setText("未选择插座")
            self.summary_status.set_badge("等待选择", C_YELLOW)
            self.summary_meta.setText("请选择左侧站点和插座。")
            return

        outlet = self._selected_outlet
        status_text = outlet.get("status_text", "未知")
        if outlet.get("is_in_progress"):
            status_text = "正在充电"
        serial = int(outlet.get("serial", 0))
        self.summary_outlet.setText(f"插座 {serial:02d} · {outlet.get('outlet_no', '')}")
        badge_color = status_color(
            "in_progress" if outlet.get("is_in_progress") else "",
            False,
            bool(outlet.get("is_in_progress")),
        )
        if not outlet.get("is_in_progress"):
            if outlet.get("status") == 3:
                badge_color = C_RED
            elif outlet.get("status") == 1:
                badge_color = C_GREEN
            else:
                badge_color = C_YELLOW
        self.summary_status.set_badge(status_text, badge_color)
        self.summary_meta.setText(
            "最近 {days} 天共 {session_count} 段会话，当前状态：{status}，最近采样时间：{last_seen}".format(
                days=self.days_spin.value(),
                session_count=len(self._sessions),
                status=status_text,
                last_seen=format_time(outlet.get("last_seen_at")),
            )
        )


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    window = HistoryWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
