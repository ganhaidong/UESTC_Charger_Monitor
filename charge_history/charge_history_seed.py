"""
生成本地演示数据，方便直接查看历史库 UI 效果。

运行：
    python charge_history_seed.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from charge_history_backend import HistoryDatabase, UTC, iso_utc, summarize_session


DB_PATH = Path(__file__).resolve().parent / "charge_history_demo.db"


def build_points(
    start: dt.datetime,
    values: List[int],
    fee_start: float,
    fee_step: float,
    interval_min: int = 6,
    used_start: int = 0,
) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    fee = fee_start
    used_min = used_start
    for index, power_w in enumerate(values):
        sample_time = start + dt.timedelta(minutes=index * interval_min)
        if index > 0:
            fee += fee_step
            used_min += interval_min
        points.append(
            {
                "sample_time": iso_utc(sample_time),
                "used_min": used_min,
                "power_w": power_w,
                "fee": round(fee, 2),
            }
        )
    return points


def session_row(
    station_id: int,
    station_name: str,
    outlet_no: str,
    serial: int,
    points: List[Dict[str, Any]],
    result: str,
    abnormal: bool,
    end_status: Optional[int],
) -> Dict[str, Any]:
    summary = summarize_session(points)
    end_time = None if result == "in_progress" else points[-1]["sample_time"]
    updated_at = points[-1]["sample_time"]
    return {
        "station_id": station_id,
        "station_name": station_name,
        "outlet_no": outlet_no,
        "serial": serial,
        "start_time": points[0]["sample_time"],
        "end_time": end_time,
        "result": result,
        "abnormal": 1 if abnormal else 0,
        "end_status": end_status,
        "duration_min": summary["duration_min"],
        "final_fee": summary["final_fee"],
        "sample_count": summary["sample_count"],
        "max_power_w": summary["max_power_w"],
        "avg_power_w": summary["avg_power_w"],
        "last_power_w": summary["last_power_w"],
        "updated_at": updated_at,
        "points": points,
    }


def seed_demo_data(db_path: Path = DB_PATH) -> None:
    db = HistoryDatabase(db_path)
    conn = db._conn

    now = dt.datetime.now(UTC).replace(second=0, microsecond=0)

    station_a_id = 990001
    station_b_id = 990002
    station_a_name = "演示站点 A · 图书馆东侧"
    station_b_name = "演示站点 B · 实验楼南门"

    sessions = [
        session_row(
            station_a_id,
            station_a_name,
            "demo-a-01",
            1,
            build_points(
                now - dt.timedelta(days=1, hours=7),
                [128, 163, 182, 196, 205, 211, 207, 191, 170, 138, 104, 72, 34, 12],
                0.35,
                0.18,
            ),
            "normal",
            False,
            1,
        ),
        session_row(
            station_a_id,
            station_a_name,
            "demo-a-01",
            1,
            build_points(
                now - dt.timedelta(hours=18),
                [136, 172, 188, 196, 204, 209, 211, 206, 180, 133, 79, 31],
                0.22,
                0.16,
            ),
            "normal",
            False,
            1,
        ),
        session_row(
            station_a_id,
            station_a_name,
            "demo-a-02",
            2,
            build_points(
                now - dt.timedelta(hours=9, minutes=20),
                [152, 186, 205, 213, 218, 221, 220, 216, 209, 204, 198],
                0.41,
                0.21,
            ),
            "abnormal",
            True,
            3,
        ),
        session_row(
            station_a_id,
            station_a_name,
            "demo-a-03",
            3,
            build_points(
                now - dt.timedelta(hours=1, minutes=18),
                [141, 170, 196, 208, 214, 218, 221, 223, 224, 225, 226, 227],
                0.18,
                0.12,
            ),
            "in_progress",
            False,
            None,
        ),
        session_row(
            station_b_id,
            station_b_name,
            "demo-b-01",
            1,
            build_points(
                now - dt.timedelta(days=2, hours=4),
                [118, 149, 173, 185, 191, 194, 188, 176, 151, 120, 88, 46, 15],
                0.28,
                0.15,
            ),
            "normal",
            False,
            1,
        ),
        session_row(
            station_b_id,
            station_b_name,
            "demo-b-02",
            2,
            build_points(
                now - dt.timedelta(hours=2, minutes=6),
                [132, 160, 181, 195, 202, 206, 211, 215, 217, 219, 220, 221, 222, 223],
                0.16,
                0.11,
            ),
            "in_progress",
            False,
            None,
        ),
        session_row(
            station_b_id,
            station_b_name,
            "demo-b-03",
            3,
            build_points(
                now - dt.timedelta(hours=30),
                [126, 152, 174, 190, 198, 205, 210, 212, 210, 190, 154, 112, 66, 19],
                0.24,
                0.17,
            ),
            "normal",
            False,
            1,
        ),
    ]

    outlets = [
        {
            "station_id": station_a_id,
            "station_name": station_a_name,
            "outlet_no": "demo-a-01",
            "serial": 1,
            "status": 1,
            "last_seen_at": iso_utc(now - dt.timedelta(minutes=2)),
            "power_w": None,
            "fee": None,
            "used_min": None,
        },
        {
            "station_id": station_a_id,
            "station_name": station_a_name,
            "outlet_no": "demo-a-02",
            "serial": 2,
            "status": 1,
            "last_seen_at": iso_utc(now - dt.timedelta(minutes=2)),
            "power_w": None,
            "fee": None,
            "used_min": None,
        },
        {
            "station_id": station_a_id,
            "station_name": station_a_name,
            "outlet_no": "demo-a-03",
            "serial": 3,
            "status": 2,
            "last_seen_at": sessions[3]["points"][-1]["sample_time"],
            "power_w": sessions[3]["last_power_w"],
            "fee": sessions[3]["final_fee"],
            "used_min": sessions[3]["duration_min"],
        },
        {
            "station_id": station_b_id,
            "station_name": station_b_name,
            "outlet_no": "demo-b-01",
            "serial": 1,
            "status": 1,
            "last_seen_at": iso_utc(now - dt.timedelta(minutes=3)),
            "power_w": None,
            "fee": None,
            "used_min": None,
        },
        {
            "station_id": station_b_id,
            "station_name": station_b_name,
            "outlet_no": "demo-b-02",
            "serial": 2,
            "status": 2,
            "last_seen_at": sessions[5]["points"][-1]["sample_time"],
            "power_w": sessions[5]["last_power_w"],
            "fee": sessions[5]["final_fee"],
            "used_min": sessions[5]["duration_min"],
        },
        {
            "station_id": station_b_id,
            "station_name": station_b_name,
            "outlet_no": "demo-b-03",
            "serial": 3,
            "status": 3,
            "last_seen_at": iso_utc(now - dt.timedelta(minutes=5)),
            "power_w": None,
            "fee": None,
            "used_min": None,
        },
    ]

    with db._lock:
        conn.execute("BEGIN")
        try:
            demo_station_ids = (station_a_id, station_b_id)
            demo_outlets = tuple(item["outlet_no"] for item in outlets)

            conn.execute(
                "DELETE FROM session_samples WHERE session_id IN (SELECT id FROM charge_sessions WHERE station_id IN (?, ?))",
                demo_station_ids,
            )
            conn.execute("DELETE FROM charge_sessions WHERE station_id IN (?, ?)", demo_station_ids)
            conn.execute("DELETE FROM outlet_samples WHERE station_id IN (?, ?)", demo_station_ids)
            conn.execute(
                "DELETE FROM outlet_registry WHERE outlet_no IN ({})".format(",".join("?" for _ in demo_outlets)),
                demo_outlets,
            )
            conn.execute("DELETE FROM station_registry WHERE station_id IN (?, ?)", demo_station_ids)

            for station_id, station_name in ((station_a_id, station_a_name), (station_b_id, station_b_name)):
                count = sum(1 for outlet in outlets if outlet["station_id"] == station_id)
                last_seen = max(
                    outlet["last_seen_at"] for outlet in outlets if outlet["station_id"] == station_id
                )
                conn.execute(
                    """
                    INSERT INTO station_registry (station_id, station_name, outlet_count, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (station_id, station_name, count, last_seen),
                )

            for outlet in outlets:
                conn.execute(
                    """
                    INSERT INTO outlet_registry (
                        outlet_no, station_id, station_name, serial, last_status, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        outlet["outlet_no"],
                        outlet["station_id"],
                        outlet["station_name"],
                        outlet["serial"],
                        outlet["status"],
                        outlet["last_seen_at"],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO outlet_samples (
                        sample_time, station_id, station_name, outlet_no, serial, status, power_w, fee, used_min
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        outlet["last_seen_at"],
                        outlet["station_id"],
                        outlet["station_name"],
                        outlet["outlet_no"],
                        outlet["serial"],
                        outlet["status"],
                        outlet["power_w"],
                        outlet["fee"],
                        outlet["used_min"],
                    ),
                )

            for item in sessions:
                cursor = conn.execute(
                    """
                    INSERT INTO charge_sessions (
                        station_id, station_name, outlet_no, serial,
                        start_time, end_time, result, abnormal, end_status,
                        duration_min, final_fee, sample_count,
                        max_power_w, avg_power_w, last_power_w, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["station_id"],
                        item["station_name"],
                        item["outlet_no"],
                        item["serial"],
                        item["start_time"],
                        item["end_time"],
                        item["result"],
                        item["abnormal"],
                        item["end_status"],
                        item["duration_min"],
                        item["final_fee"],
                        item["sample_count"],
                        item["max_power_w"],
                        item["avg_power_w"],
                        item["last_power_w"],
                        item["updated_at"],
                    ),
                )
                session_id = cursor.lastrowid
                for point in item["points"]:
                    conn.execute(
                        """
                        INSERT INTO session_samples (
                            session_id, sample_time, used_min, power_w, fee
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            point["sample_time"],
                            point["used_min"],
                            point["power_w"],
                            point["fee"],
                        ),
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            db.close()

    print(f"已写入演示数据: {db_path}")
    print("演示站点:")
    print(f"- {station_a_name}")
    print(f"- {station_b_name}")


if __name__ == "__main__":
    seed_demo_data()
