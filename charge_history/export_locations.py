"""
export_locations.py — 导出所有站点的位置表（station_locations.json）

数据来源：wemp.issks.com 的“按经纬度查周边站点”接口（与 station_picker.py 同源）。
每个站点返回 stationId / stationName / address / latitude / longitude，用于在真实地图上标定。

用法：
    python charge_history/export_locations.py

输出：
    charge_history/station_locations.json
        [
          {"station_id": 120204, "station_name": "...", "address": "...",
           "latitude": ..., "longitude": ..., "free_num": ...},
          ...
        ]
"""

from __future__ import annotations

import json
import sys
import requests
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
OUT = RUNTIME_DIR / "station_locations.json"
ALL_JSON = RUNTIME_DIR / "all.json"

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
    "accept": "*/*",
    "origin": "https://api.issks.com",
    "x-requested-with": "com.tencent.mm",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://api.issks.com/",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

NEAR_URL = "https://wemp.issks.com/device/v1/near/station"
# 校园中心点（与 station_picker.py 一致）
BASE = {"latitude": 30.74566536567867, "longitude": 103.92188101700906}


def fetch_page(page: int, page_size: int, scale: int) -> list[dict]:
    payload = {
        "page": page,
        "pageSize": page_size,
        "scale": scale,
        "latitude": BASE["latitude"],
        "longitude": BASE["longitude"],
        "userLatitude": BASE["latitude"],
        "userLongitude": BASE["longitude"],
    }
    resp = requests.post(NEAR_URL, headers=HEADERS, json=payload, timeout=20, proxies={"http": None, "https": None})
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return data.get("elecStationData", [])


def main() -> int:
    all_map = {}
    if ALL_JSON.exists():
        all_map = json.loads(ALL_JSON.read_text(encoding="utf-8"))

    # 用两个尺度各抓一遍，尽量覆盖更多站点
    seen = {}
    for scale in (3, 5):
        for page in range(1, 6):
            try:
                rows = fetch_page(page, 200, scale)
            except Exception as exc:
                print(f"[!] scale={scale} page={page} 请求失败：{exc}")
                continue
            if not rows:
                break
            for s in rows:
                sid = s.get("stationId")
                if sid is None:
                    continue
                seen[sid] = {
                    "station_id": sid,
                    "station_name": s.get("stationName", ""),
                    "address": s.get("address", ""),
                    "latitude": s.get("latitude"),
                    "longitude": s.get("longitude"),
                    "free_num": s.get("freeNum", 0),
                }
            if len(rows) < 200:
                break

    locations = list(seen.values())
    OUT.write_text(json.dumps(locations, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"导出了 {len(locations)} 个站点 -> {OUT.name}")
    ids = set(seen.keys())
    missing = [f"{sid:>8}  {name}" for name, sid in all_map.items() if sid not in ids]
    if missing:
        print(f"all.json 中不在坐标表里的站点（{len(missing)} 个）：")
        for m in missing:
            print("   ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
