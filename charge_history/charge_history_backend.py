"""
充电桩三天历史后端。

职责：
1. 读取 all.json 的站点列表。
2. 复用 charger_api.fetch_station(...) 周期性采样所有站点的所有充电桩。
3. 将分钟级采样写入 SQLite，并自动切分出每段充电会话。
4. 提供给 PyQt5 查询端使用的本地 HTTP JSON 接口。

默认启动：
    python charge_history_backend.py

默认监听：
    http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hmac
import json
import os
import ssl
import sqlite3
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

RUNTIME_DIR = Path(__file__).resolve().parent
WEB_DIR = RUNTIME_DIR / "web"
from charger_api import fetch_station


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
}


STATUS_FREE = 1
STATUS_BUSY = 2
STATUS_BROKEN = 3
STATUS_TEXT = {
    STATUS_FREE: "空闲",
    STATUS_BUSY: "充电中",
    STATUS_BROKEN: "故障",
}

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_SAMPLE_INTERVAL_S = 60
DEFAULT_RETENTION_DAYS = 3
DEFAULT_STATION_WORKERS = 8
UTC = dt.timezone.utc


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso_utc(value: Optional[dt.datetime] = None) -> str:
    value = value or utc_now()
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    return dt.datetime.fromisoformat(value)


def clamp_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clamp_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calc_baseline_power(points: List[Dict[str, Any]]) -> float:
    powers = [pt["power_w"] for pt in points if pt.get("power_w") is not None]
    if not powers:
        return 150.0
    window = min(8, len(powers))
    stable_ratio = 0.25
    for idx in range(0, len(powers) - window + 1):
        chunk = powers[idx:idx + window]
        mean_power = sum(chunk) / len(chunk)
        if mean_power <= 0:
            continue
        power_range = max(chunk) - min(chunk)
        if power_range / mean_power < stable_ratio:
            return mean_power
    return max(sum(powers[:window]) / window, 150.0)


def summarize_session(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not points:
        return {
            "sample_count": 0,
            "duration_min": 0,
            "max_power_w": None,
            "avg_power_w": None,
            "last_power_w": None,
            "final_fee": None,
        }

    powers = [pt["power_w"] for pt in points if pt.get("power_w") is not None]
    used_minutes = [pt["used_min"] for pt in points if pt.get("used_min") is not None]
    duration_min = 0
    if used_minutes:
        duration_min = max(0, used_minutes[-1])
    else:
        started_at = parse_iso(points[0]["sample_time"])
        ended_at = parse_iso(points[-1]["sample_time"])
        if started_at and ended_at:
            duration_min = max(0, int((ended_at - started_at).total_seconds() // 60))

    return {
        "sample_count": len(points),
        "duration_min": duration_min,
        "max_power_w": max(powers) if powers else None,
        "avg_power_w": round(sum(powers) / len(powers), 1) if powers else None,
        "last_power_w": powers[-1] if powers else None,
        "final_fee": points[-1].get("fee"),
    }


def detect_abnormal_end(points: List[Dict[str, Any]], final_status: Optional[int]) -> bool:
    if final_status == STATUS_BROKEN:
        return True

    powers = [pt["power_w"] for pt in points if pt.get("power_w") is not None]
    if len(powers) < 5:
        return False

    baseline = calc_baseline_power(points)
    low_threshold = baseline * 0.4
    if powers[-1] >= low_threshold:
        return True

    smooth_n = min(3, len(powers))
    smoothed = [
        sum(powers[i:i + smooth_n]) / smooth_n
        for i in range(0, len(powers) - smooth_n + 1)
    ]
    if not smoothed:
        return False

    drop_start_threshold = baseline * 0.3
    tail_value = smoothed[-1]
    drop_start_idx = 0
    for idx in range(len(smoothed) - 2, -1, -1):
        if smoothed[idx] - tail_value >= drop_start_threshold:
            drop_start_idx = idx
            break

    drop_points = points[drop_start_idx:]
    if len(drop_points) < 4:
        return True

    start_used = next((pt["used_min"] for pt in drop_points if pt.get("used_min") is not None), None)
    end_used = next((pt["used_min"] for pt in reversed(drop_points) if pt.get("used_min") is not None), None)
    if start_used is not None and end_used is not None and (end_used - start_used) < 4:
        return True

    return False


def session_result(points: List[Dict[str, Any]], final_status: Optional[int], ended: bool) -> tuple[str, bool]:
    if not ended:
        return "in_progress", False
    abnormal = detect_abnormal_end(points, final_status)
    return ("abnormal" if abnormal else "normal"), abnormal


def resolve_local_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent / path


def load_station_map(path: Path, limit: Optional[int] = None) -> Dict[str, int]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    items = list(data.items())
    if limit:
        items = items[:limit]
    return {name: int(station_id) for name, station_id in items}


_LOCATIONS_CACHE: Optional[List[Dict[str, Any]]] = None


def load_locations() -> List[Dict[str, Any]]:
    """读取站点位置表（station_locations.json），供 /api/locations 使用。"""
    global _LOCATIONS_CACHE
    if _LOCATIONS_CACHE is not None:
        return _LOCATIONS_CACHE
    path = RUNTIME_DIR / "station_locations.json"
    if path.exists():
        try:
            _LOCATIONS_CACHE = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _LOCATIONS_CACHE = []
    else:
        _LOCATIONS_CACHE = []
    return _LOCATIONS_CACHE


def estimate_session_start(sample_time: str, used_min: Optional[int]) -> str:
    if used_min is None or used_min <= 0:
        return sample_time
    sample_dt = parse_iso(sample_time)
    if sample_dt is None:
        return sample_time
    delta_min = max(0, min(used_min, 7 * 24 * 60))
    return iso_utc(sample_dt - dt.timedelta(minutes=delta_min))


def looks_like_new_session(
    last_used_min: Optional[int],
    current_used_min: Optional[int],
    last_fee: Optional[float],
    current_fee: Optional[float],
) -> bool:
    if (
        last_used_min is not None
        and current_used_min is not None
        and current_used_min + 2 < last_used_min
    ):
        return True
    if last_fee is not None and current_fee is not None and (current_fee + 0.5) < last_fee:
        return True
    return False


class HistoryDatabase:
    def __init__(self, db_path: Path):
        self.path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS station_registry (
                station_id INTEGER PRIMARY KEY,
                station_name TEXT NOT NULL,
                outlet_count INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS outlet_registry (
                outlet_no TEXT PRIMARY KEY,
                station_id INTEGER NOT NULL,
                station_name TEXT NOT NULL,
                serial INTEGER NOT NULL,
                last_status INTEGER NOT NULL,
                last_seen_at TEXT,
                UNIQUE (station_id, serial)
            );

            CREATE TABLE IF NOT EXISTS outlet_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_time TEXT NOT NULL,
                station_id INTEGER NOT NULL,
                station_name TEXT NOT NULL,
                outlet_no TEXT NOT NULL,
                serial INTEGER NOT NULL,
                status INTEGER NOT NULL,
                power_w INTEGER,
                fee REAL,
                used_min INTEGER,
                UNIQUE (sample_time, outlet_no)
            );

            CREATE INDEX IF NOT EXISTS idx_outlet_samples_outlet_time
            ON outlet_samples (outlet_no, sample_time DESC);

            CREATE INDEX IF NOT EXISTS idx_outlet_samples_station_time
            ON outlet_samples (station_id, sample_time DESC);

            CREATE TABLE IF NOT EXISTS charge_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id INTEGER NOT NULL,
                station_name TEXT NOT NULL,
                outlet_no TEXT NOT NULL,
                serial INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                result TEXT NOT NULL DEFAULT 'in_progress',
                abnormal INTEGER NOT NULL DEFAULT 0,
                end_status INTEGER,
                duration_min INTEGER,
                final_fee REAL,
                sample_count INTEGER NOT NULL DEFAULT 0,
                max_power_w INTEGER,
                avg_power_w REAL,
                last_power_w INTEGER,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_charge_sessions_outlet_time
            ON charge_sessions (outlet_no, start_time DESC);

            CREATE INDEX IF NOT EXISTS idx_charge_sessions_station_time
            ON charge_sessions (station_id, start_time DESC);

            CREATE TABLE IF NOT EXISTS session_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                sample_time TEXT NOT NULL,
                used_min INTEGER,
                power_w INTEGER,
                fee REAL,
                UNIQUE (session_id, sample_time),
                FOREIGN KEY (session_id) REFERENCES charge_sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_session_samples_session_time
            ON session_samples (session_id, sample_time ASC);

            CREATE TABLE IF NOT EXISTS service_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO service_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            self._conn.commit()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM service_meta WHERE key = ?",
                (key,),
            ).fetchone()
        return row["value"] if row else default

    def totals(self) -> Dict[str, int]:
        with self._lock:
            station_count = self._conn.execute("SELECT COUNT(*) AS n FROM station_registry").fetchone()["n"]
            outlet_count = self._conn.execute("SELECT COUNT(*) AS n FROM outlet_registry").fetchone()["n"]
            session_count = self._conn.execute("SELECT COUNT(*) AS n FROM charge_sessions").fetchone()["n"]
            active_sessions = self._conn.execute(
                "SELECT COUNT(*) AS n FROM charge_sessions WHERE end_time IS NULL"
            ).fetchone()["n"]
        return {
            "station_count": station_count,
            "outlet_count": outlet_count,
            "session_count": session_count,
            "active_sessions": active_sessions,
        }

    def record_station_snapshot(
        self,
        station_name: str,
        station_id: int,
        outlets: List[Dict[str, Any]],
        sample_time: str,
    ) -> None:
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                self._conn.execute(
                    """
                    INSERT INTO station_registry (station_id, station_name, outlet_count, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(station_id) DO UPDATE SET
                        station_name = excluded.station_name,
                        outlet_count = excluded.outlet_count,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (station_id, station_name, len(outlets), sample_time),
                )
                for outlet in outlets:
                    self._record_outlet_sample_locked(station_name, station_id, outlet, sample_time)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _record_outlet_sample_locked(
        self,
        station_name: str,
        station_id: int,
        outlet: Dict[str, Any],
        sample_time: str,
    ) -> None:
        serial = clamp_int(outlet.get("serial")) or 0
        outlet_no = str(outlet.get("outletNo") or f"{station_id}-{serial}")
        status = clamp_int(outlet.get("status")) or STATUS_BROKEN
        power_w = clamp_int(outlet.get("power_w"))
        fee = clamp_float(outlet.get("fee"))
        used_min = clamp_int(outlet.get("used_min"))

        self._conn.execute(
            """
            INSERT INTO outlet_registry (
                outlet_no, station_id, station_name, serial, last_status, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(outlet_no) DO UPDATE SET
                station_id = excluded.station_id,
                station_name = excluded.station_name,
                serial = excluded.serial,
                last_status = excluded.last_status,
                last_seen_at = excluded.last_seen_at
            """,
            (outlet_no, station_id, station_name, serial, status, sample_time),
        )

        self._conn.execute(
            """
            INSERT OR IGNORE INTO outlet_samples (
                sample_time, station_id, station_name, outlet_no, serial, status, power_w, fee, used_min
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sample_time, station_id, station_name, outlet_no, serial, status, power_w, fee, used_min),
        )

        open_session = self._conn.execute(
            """
            SELECT * FROM charge_sessions
            WHERE outlet_no = ? AND end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
            """,
            (outlet_no,),
        ).fetchone()

        if status == STATUS_BUSY:
            if open_session is not None:
                last_point = self._load_last_session_point_locked(open_session["id"])
                if last_point and looks_like_new_session(
                    last_used_min=last_point.get("used_min"),
                    current_used_min=used_min,
                    last_fee=last_point.get("fee"),
                    current_fee=fee,
                ):
                    estimated_start = estimate_session_start(sample_time, used_min)
                    prior_end = estimated_start
                    last_sample_time = parse_iso(last_point.get("sample_time"))
                    prior_end_dt = parse_iso(prior_end)
                    if last_sample_time and prior_end_dt and prior_end_dt <= last_sample_time:
                        prior_end = sample_time
                    self._finalize_session_locked(open_session["id"], prior_end, STATUS_FREE)
                    open_session = None

            if open_session is None:
                cur = self._conn.execute(
                    """
                    INSERT INTO charge_sessions (
                        station_id, station_name, outlet_no, serial,
                        start_time, end_time, result, abnormal,
                        end_status, duration_min, final_fee, sample_count,
                        max_power_w, avg_power_w, last_power_w, updated_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, 'in_progress', 0, NULL, 0, ?, 0, NULL, NULL, ?, ?)
                    """,
                    (
                        station_id,
                        station_name,
                        outlet_no,
                        serial,
                        estimate_session_start(sample_time, used_min),
                        fee,
                        power_w,
                        sample_time,
                    ),
                )
                session_id = cur.lastrowid
            else:
                session_id = open_session["id"]
                self._conn.execute(
                    """
                    UPDATE charge_sessions
                    SET station_id = ?, station_name = ?, serial = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (station_id, station_name, serial, sample_time, session_id),
                )

            self._conn.execute(
                """
                INSERT OR IGNORE INTO session_samples (
                    session_id, sample_time, used_min, power_w, fee
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, sample_time, used_min, power_w, fee),
            )

            points = self._load_session_points_locked(session_id)
            summary = summarize_session(points)
            self._conn.execute(
                """
                UPDATE charge_sessions
                SET result = 'in_progress',
                    abnormal = 0,
                    end_time = NULL,
                    end_status = NULL,
                    duration_min = ?,
                    final_fee = ?,
                    sample_count = ?,
                    max_power_w = ?,
                    avg_power_w = ?,
                    last_power_w = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    summary["duration_min"],
                    summary["final_fee"],
                    summary["sample_count"],
                    summary["max_power_w"],
                    summary["avg_power_w"],
                    summary["last_power_w"],
                    sample_time,
                    session_id,
                ),
            )
            return

        if open_session is None:
            return
        self._finalize_session_locked(open_session["id"], sample_time, status)

    def _load_session_points_locked(self, session_id: int) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT sample_time, used_min, power_w, fee
            FROM session_samples
            WHERE session_id = ?
            ORDER BY sample_time ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _load_last_session_point_locked(self, session_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            """
            SELECT sample_time, used_min, power_w, fee
            FROM session_samples
            WHERE session_id = ?
            ORDER BY sample_time DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        return dict(row) if row else None

    def _finalize_session_locked(
        self,
        session_id: int,
        end_time: str,
        final_status: int,
    ) -> None:
        points = self._load_session_points_locked(session_id)
        summary = summarize_session(points)
        result, abnormal = session_result(points, final_status, ended=True)
        self._conn.execute(
            """
            UPDATE charge_sessions
            SET end_time = ?,
                result = ?,
                abnormal = ?,
                end_status = ?,
                duration_min = ?,
                final_fee = ?,
                sample_count = ?,
                max_power_w = ?,
                avg_power_w = ?,
                last_power_w = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                end_time,
                result,
                1 if abnormal else 0,
                final_status,
                summary["duration_min"],
                summary["final_fee"],
                summary["sample_count"],
                summary["max_power_w"],
                summary["avg_power_w"],
                summary["last_power_w"],
                end_time,
                session_id,
            ),
        )

    def cleanup_old_data(self, retention_days: int) -> None:
        cutoff = iso_utc(utc_now() - dt.timedelta(days=retention_days))
        with self._lock:
            self._conn.execute(
                "DELETE FROM charge_sessions WHERE end_time IS NOT NULL AND end_time < ?",
                (cutoff,),
            )
            self._conn.execute(
                "DELETE FROM outlet_samples WHERE sample_time < ?",
                (cutoff,),
            )
            self._conn.commit()

    def list_stations(self, search: str = "") -> List[Dict[str, Any]]:
        like_kw = f"%{search.strip()}%"
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    s.station_id,
                    s.station_name,
                    s.outlet_count,
                    s.last_seen_at,
                    COALESCE(SUM(CASE WHEN o.last_status = 2 THEN 1 ELSE 0 END), 0) AS busy_count,
                    COALESCE(SUM(CASE WHEN o.last_status = 3 THEN 1 ELSE 0 END), 0) AS broken_count,
                    COALESCE(SUM(CASE WHEN cs.id IS NOT NULL THEN 1 ELSE 0 END), 0) AS in_progress_count
                FROM station_registry s
                LEFT JOIN outlet_registry o
                    ON o.station_id = s.station_id
                LEFT JOIN charge_sessions cs
                    ON cs.outlet_no = o.outlet_no AND cs.end_time IS NULL
                WHERE s.station_name LIKE ?
                GROUP BY s.station_id, s.station_name, s.outlet_count, s.last_seen_at
                ORDER BY s.station_name
                """,
                (like_kw,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_outlets(self, station_id: int, search: str = "") -> List[Dict[str, Any]]:
        like_kw = f"%{search.strip()}%"
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    o.station_id,
                    o.station_name,
                    o.outlet_no,
                    o.serial,
                    o.last_status AS status,
                    o.last_seen_at,
                    cs.id AS current_session_id,
                    cs.start_time AS current_session_start,
                    cs.sample_count AS current_sample_count,
                    cs.last_power_w AS current_power_w,
                    cs.final_fee AS current_fee
                FROM outlet_registry o
                LEFT JOIN charge_sessions cs
                    ON cs.outlet_no = o.outlet_no AND cs.end_time IS NULL
                WHERE o.station_id = ?
                  AND (
                    ? = '%%'
                    OR CAST(o.serial AS TEXT) LIKE ?
                    OR o.outlet_no LIKE ?
                  )
                ORDER BY o.serial ASC, o.outlet_no ASC
                """,
                (station_id, like_kw, like_kw, like_kw),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["status_text"] = STATUS_TEXT.get(item["status"], "未知")
            item["is_in_progress"] = bool(item["current_session_id"])
            items.append(item)
        return items

    def list_sessions(self, station_id: int, outlet_no: str, days: int = 3) -> List[Dict[str, Any]]:
        cutoff = iso_utc(utc_now() - dt.timedelta(days=max(1, days)))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    id,
                    station_id,
                    station_name,
                    outlet_no,
                    serial,
                    start_time,
                    end_time,
                    result,
                    abnormal,
                    end_status,
                    duration_min,
                    final_fee,
                    sample_count,
                    max_power_w,
                    avg_power_w,
                    last_power_w,
                    updated_at
                FROM charge_sessions
                WHERE station_id = ?
                  AND outlet_no = ?
                  AND (
                    end_time IS NULL
                    OR end_time >= ?
                    OR start_time >= ?
                  )
                ORDER BY
                    CASE WHEN end_time IS NULL THEN 0 ELSE 1 END,
                    COALESCE(end_time, updated_at) DESC,
                    start_time DESC
                """,
                (station_id, outlet_no, cutoff, cutoff),
            ).fetchall()

        items = []
        for row in rows:
            item = dict(row)
            item["abnormal"] = bool(item["abnormal"])
            item["status_text"] = self._session_status_text(item)
            item["is_in_progress"] = item["end_time"] is None or item["result"] == "in_progress"
            items.append(item)
        return items

    def get_session_detail(self, session_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    station_id,
                    station_name,
                    outlet_no,
                    serial,
                    start_time,
                    end_time,
                    result,
                    abnormal,
                    end_status,
                    duration_min,
                    final_fee,
                    sample_count,
                    max_power_w,
                    avg_power_w,
                    last_power_w,
                    updated_at
                FROM charge_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            points = self._load_session_points_locked(session_id)

        item = dict(row)
        item["abnormal"] = bool(item["abnormal"])
        item["status_text"] = self._session_status_text(item)
        item["is_in_progress"] = item["end_time"] is None or item["result"] == "in_progress"
        item["points"] = points
        item["baseline_power_w"] = round(calc_baseline_power(points), 1) if points else None
        return item

    @staticmethod
    def _session_status_text(item: Dict[str, Any]) -> str:
        if item["result"] == "in_progress" or item.get("end_time") is None:
            return "正在充电"
        if item.get("abnormal"):
            return "异常结束"
        return "正常结束"


class HistoryCollector:
    def __init__(
        self,
        station_map: Dict[str, int],
        database: HistoryDatabase,
        sample_interval_s: int,
        retention_days: int,
        station_workers: int,
        auto_collect: bool = True,
    ):
        self.station_map = station_map
        self.database = database
        self.sample_interval_s = max(5, sample_interval_s)
        self.retention_days = max(1, retention_days)
        self.station_workers = max(1, station_workers)
        self.auto_collect = auto_collect
        self._stop_event = threading.Event()
        self._loop_thread: Optional[threading.Thread] = None
        self._run_lock = threading.Lock()
        self._last_run_started_at: Optional[str] = None
        self._last_run_finished_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_summary: Dict[str, Any] = {}

    def start(self) -> None:
        if not self.auto_collect:
            return
        if self._loop_thread and self._loop_thread.is_alive():
            return
        self._loop_thread = threading.Thread(target=self._loop, name="history-collector", daemon=True)
        self._loop_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)

    def is_collecting(self) -> bool:
        return self._run_lock.locked()

    def status_snapshot(self) -> Dict[str, Any]:
        return {
            "sample_interval_s": self.sample_interval_s,
            "retention_days": self.retention_days,
            "station_workers": self.station_workers,
            "station_total": len(self.station_map),
            "auto_collect": self.auto_collect,
            "is_collecting": self.is_collecting(),
            "last_run_started_at": self._last_run_started_at,
            "last_run_finished_at": self._last_run_finished_at,
            "last_error": self._last_error,
            "last_summary": self._last_summary,
            "database": str(self.database.path),
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            if self._stop_event.wait(self.sample_interval_s):
                break

    def run_once(self) -> Dict[str, Any]:
        if not self._run_lock.acquire(blocking=False):
            return {
                "status": "busy",
                "message": "采集任务正在进行中",
                "started_at": self._last_run_started_at,
            }

        started_at = iso_utc()
        self._last_run_started_at = started_at
        self._last_error = None
        self.database.set_meta("last_collection_started_at", started_at)
        print(f"[history] collect started at {started_at}")

        try:
            futures = {}
            results = []
            station_items = list(self.station_map.items())
            worker_count = min(self.station_workers, max(1, len(station_items)))

            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                for station_name, station_id in station_items:
                    futures[executor.submit(fetch_station, station_id)] = (station_name, station_id)

                for future in as_completed(futures):
                    station_name, station_id = futures[future]
                    try:
                        outlets = future.result()
                        results.append(
                            {
                                "station_name": station_name,
                                "station_id": station_id,
                                "outlets": outlets,
                                "error": None,
                            }
                        )
                    except Exception as exc:
                        results.append(
                            {
                                "station_name": station_name,
                                "station_id": station_id,
                                "outlets": None,
                                "error": str(exc),
                            }
                        )

            sample_time = iso_utc()
            station_ok = 0
            station_failed = 0
            outlet_total = 0
            busy_total = 0
            failed_stations = []

            for item in sorted(results, key=lambda val: val["station_name"]):
                if item["outlets"] is None:
                    station_failed += 1
                    failed_stations.append(
                        {
                            "station_name": item["station_name"],
                            "station_id": item["station_id"],
                            "error": item["error"] or "接口返回空数据",
                        }
                    )
                    continue

                station_ok += 1
                outlet_total += len(item["outlets"])
                busy_total += sum(1 for outlet in item["outlets"] if (outlet.get("status") == STATUS_BUSY))
                self.database.record_station_snapshot(
                    station_name=item["station_name"],
                    station_id=item["station_id"],
                    outlets=item["outlets"],
                    sample_time=sample_time,
                )

            self.database.cleanup_old_data(self.retention_days)
            finished_at = iso_utc()
            summary = {
                "status": "ok",
                "started_at": started_at,
                "finished_at": finished_at,
                "sample_time": sample_time,
                "station_total": len(station_items),
                "station_ok": station_ok,
                "station_failed": station_failed,
                "outlet_total": outlet_total,
                "busy_total": busy_total,
                "failed_stations": failed_stations[:12],
            }
            self._last_run_finished_at = finished_at
            self._last_summary = summary
            self.database.set_meta("last_collection_finished_at", finished_at)
            self.database.set_meta("last_collection_summary", json.dumps(summary, ensure_ascii=False))
            self.database.set_meta("last_collection_error", "")
            print(
                f"[history] collect finished: ok={station_ok}, failed={station_failed}, "
                f"outlets={outlet_total}, busy={busy_total}"
            )
            return summary
        except Exception:
            self._last_error = traceback.format_exc()
            self.database.set_meta("last_collection_error", self._last_error)
            print("[history] collect failed")
            print(self._last_error)
            return {
                "status": "error",
                "started_at": started_at,
                "error": self._last_error,
            }
        finally:
            self._run_lock.release()


class HistoryService:
    def __init__(self, args: argparse.Namespace):
        self.station_file = resolve_local_path(args.stations)
        self.db_path = resolve_local_path(args.db)
        self.station_map = load_station_map(self.station_file, args.station_limit)
        self.database = HistoryDatabase(self.db_path)
        self.collector = HistoryCollector(
            station_map=self.station_map,
            database=self.database,
            sample_interval_s=args.sample_interval,
            retention_days=args.retention_days,
            station_workers=args.station_workers,
            auto_collect=not args.no_collector,
        )

    def start(self) -> None:
        self.collector.start()

    def stop(self) -> None:
        self.collector.stop()
        self.database.close()

    def health(self) -> Dict[str, Any]:
        return {
            "station_file": str(self.station_file),
            "collector": self.collector.status_snapshot(),
            "totals": self.database.totals(),
        }


class HistoryRequestHandler(BaseHTTPRequestHandler):
    service: Optional[HistoryService] = None
    # 管理接口口令（Basic Auth）：None 表示未配置。由 serve_forever 从环境变量注入。
    # 只作用于 /api/admin/*（如 /api/admin/collect）；普通查询接口不鉴权、全开放。
    auth_user: Optional[str] = None
    auth_pass: Optional[str] = None
    # 按 IP 限流：rate_window 秒内每个 IP 最多 rate_limit 次请求；0 表示不限。
    rate_limit: int = 0
    rate_window: int = 60
    _hits: Dict[str, "deque[float]"] = {}
    _hits_lock = threading.Lock()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if not self._check_rate_limit():
            return
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            path = parsed.path.rstrip("/") or "/"

            # 管理接口需要口令；未配置口令则直接关闭，避免公网被随意触发。
            if path.startswith("/api/admin"):
                if not self._require_admin_auth():
                    return

            if path == "/" or path == "/index.html":
                if self._serve_static("index.html"):
                    return
                self._write_json(
                    200,
                    {
                        "ok": True,
                        "data": {
                            "name": "charge-history-backend",
                            "health": "/api/health",
                            "stations": "/api/stations",
                            "outlets": "/api/outlets?station_id=120204",
                            "sessions": "/api/sessions?station_id=120204&outlet_no=O22071401189593&days=3",
                            "session": "/api/session?session_id=1",
                            "collect": "/api/admin/collect",
                        },
                    },
                )
                return

            if self.service is None:
                self._write_json(500, {"ok": False, "error": "服务未初始化"})
                return

            if path == "/api/health":
                self._write_json(200, {"ok": True, "data": self.service.health()})
                return

            if path == "/api/stations":
                search = self._query_one(query, "search", "")
                data = self.service.database.list_stations(search=search)
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/outlets":
                station_id = int(self._query_one(query, "station_id"))
                search = self._query_one(query, "search", "")
                data = self.service.database.list_outlets(station_id=station_id, search=search)
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/sessions":
                station_id = int(self._query_one(query, "station_id"))
                outlet_no = self._query_one(query, "outlet_no")
                days = int(self._query_one(query, "days", "3"))
                data = self.service.database.list_sessions(
                    station_id=station_id,
                    outlet_no=outlet_no,
                    days=days,
                )
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/session":
                session_id = int(self._query_one(query, "session_id"))
                data = self.service.database.get_session_detail(session_id)
                if data is None:
                    self._write_json(404, {"ok": False, "error": "会话不存在"})
                    return
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/admin/collect":
                data = self.service.collector.run_once()
                self._write_json(200, {"ok": True, "data": data})
                return

            if path == "/api/locations":
                self._write_json(200, {"ok": True, "data": load_locations()})
                return

            if self._serve_static(path.lstrip("/")):
                return
            self._write_json(404, {"ok": False, "error": f"未知接口: {path}"})
        except ValueError as exc:
            self._write_json(400, {"ok": False, "error": str(exc)})
        except Exception:
            self._write_json(
                500,
                {
                    "ok": False,
                    "error": traceback.format_exc(limit=3),
                },
            )

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[http] {self.address_string()} - {fmt % args}")

    @staticmethod
    def _query_one(query: Dict[str, List[str]], key: str, default: Optional[str] = None) -> str:
        values = query.get(key)
        if not values:
            if default is None:
                raise ValueError(f"缺少参数: {key}")
            return default
        return values[0]

    def _send_common_headers(self) -> None:
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _check_rate_limit(self) -> bool:
        """按 IP 限流：窗口内超过阈值则返回 429。rate_limit=0 时不限。"""
        if not self.rate_limit:
            return True
        ip = self.client_address[0] if self.client_address else "?"
        now = time.time()
        with self._hits_lock:
            dq = self._hits.setdefault(ip, deque())
            while dq and dq[0] <= now - self.rate_window:
                dq.popleft()
            if len(dq) >= self.rate_limit:
                self._send_too_many()
                return False
            dq.append(now)
            # 内存保护：列表过大时清理空桶
            if len(self._hits) > 10000 and dq is not None:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
        return True

    def _send_too_many(self) -> None:
        body = json.dumps({"ok": False, "error": "访问过于频繁，请稍后再试"}, ensure_ascii=False).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_admin_auth(self) -> bool:
        """仅 /api/admin/* 需要口令；未配置口令时直接关闭（403）。"""
        if not self.auth_user:
            self._send_forbidden("手动采集已关闭（未配置管理口令）")
            return False
        header = self.headers.get("Authorization")
        if header and header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
                user, _, pw = decoded.partition(":")
            except Exception:
                user, pw = "", ""
            if (
                hmac.compare_digest(user, self.auth_user)
                and hmac.compare_digest(pw, self.auth_pass or "")
            ):
                return True
        self._send_auth_challenge()
        return False

    def _send_forbidden(self, msg: str) -> None:
        body = json.dumps({"ok": False, "error": msg}, ensure_ascii=False).encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_auth_challenge(self) -> None:
        body = json.dumps({"ok": False, "error": "需要管理口令"}, ensure_ascii=False).encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="charger-monitor", charset="UTF-8"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, rel_path: str) -> bool:
        """从 WEB_DIR 提供静态文件；找不到返回 False。"""
        if not WEB_DIR.is_dir():
            return False
        rel_path = rel_path or "index.html"
        candidate = (WEB_DIR / rel_path).resolve()
        try:
            candidate.relative_to(WEB_DIR.resolve())
        except ValueError:
            return False
        if not candidate.is_file():
            return False
        ext = candidate.suffix.lower()
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
        try:
            body = candidate.read_bytes()
        except OSError:
            return False
        self._write_bytes(200, body, content_type)
        return True


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="充电桩三天历史后端")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口，默认 8765")
    parser.add_argument(
        "--stations",
        default=str(RUNTIME_DIR / "all.json"),
        help="站点清单 JSON，默认脚本同目录下的 all.json",
    )
    parser.add_argument(
        "--db",
        default=str(RUNTIME_DIR / "charge_history.db"),
        help="SQLite 数据库路径，默认脚本同目录下的 charge_history.db",
    )
    parser.add_argument(
        "--sample-interval",
        type=int,
        default=DEFAULT_SAMPLE_INTERVAL_S,
        help="采样间隔秒数，默认 60。测试时可临时改小。",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="数据库保留天数，默认 3",
    )
    parser.add_argument(
        "--station-workers",
        type=int,
        default=DEFAULT_STATION_WORKERS,
        help="站点并发采样线程数，默认 8",
    )
    parser.add_argument(
        "--station-limit",
        type=int,
        default=None,
        help="仅采样前 N 个站点，方便本地压测和调试",
    )
    parser.add_argument(
        "--no-collector",
        action="store_true",
        help="只启动接口服务，不自动循环采样",
    )
    parser.add_argument("--ssl-cert", default=None, help="HTTPS 证书文件路径，例如 fullchain.pem")
    parser.add_argument("--ssl-key", default=None, help="HTTPS 私钥文件路径，例如 privkey.pem")
    return parser


def serve_forever(args: argparse.Namespace) -> None:
    service = HistoryService(args)
    HistoryRequestHandler.service = service

    # 管理口令（仅作用于 /api/admin/*）：设置 CHARGER_AUTH_USER / CHARGER_AUTH_PASS 即启用。
    auth_user = os.environ.get("CHARGER_AUTH_USER")
    auth_pass = os.environ.get("CHARGER_AUTH_PASS")
    if bool(auth_user) ^ bool(auth_pass):
        print("[history] 警告: CHARGER_AUTH_USER 与 CHARGER_AUTH_PASS 必须同时设置，本次管理接口将被关闭")
        auth_user = auth_pass = None
    HistoryRequestHandler.auth_user = auth_user
    HistoryRequestHandler.auth_pass = auth_pass

    # 按 IP 限流：CHARGER_RATE_LIMIT=每 IP 每窗口最大请求数(默认600)，CHARGER_RATE_WINDOW=窗口秒数(默认60)。设为0表示不限。
    try:
        rate_limit = int(os.environ.get("CHARGER_RATE_LIMIT", "600"))
        rate_window = int(os.environ.get("CHARGER_RATE_WINDOW", "60"))
    except ValueError:
        rate_limit, rate_window = 600, 60
    HistoryRequestHandler.rate_limit = max(0, rate_limit)
    HistoryRequestHandler.rate_window = max(1, rate_window)

    server = ThreadingHTTPServer((args.host, args.port), HistoryRequestHandler)
    server.daemon_threads = True
    scheme = "http"

    if args.ssl_cert and args.ssl_key:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    print(f"[history] station file: {service.station_file}")
    print(f"[history] database    : {service.db_path}")
    print(f"[history] stations    : {len(service.station_map)}")
    print(f"[history] listen      : {scheme}://{args.host}:{args.port}")
    print(f"[history] admin-auth  : {'on (' + (auth_user or '') + ') 仅 /api/admin/*' if auth_user else 'off (管理接口已关闭)'}")
    print(f"[history] rate-limit  : {HistoryRequestHandler.rate_limit} req/{HistoryRequestHandler.rate_window}s per IP" +
          (" (disabled)" if not HistoryRequestHandler.rate_limit else ""))
    if args.no_collector:
        print("[history] collector   : disabled")
    else:
        print(f"[history] collector   : every {service.collector.sample_interval_s}s")

    service.start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[history] stopping...")
    finally:
        server.shutdown()
        server.server_close()
        service.stop()


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    if bool(args.ssl_cert) ^ bool(args.ssl_key):
        parser.error("--ssl-cert 和 --ssl-key 必须同时提供，或者都不提供")
    serve_forever(args)


if __name__ == "__main__":
    main()
