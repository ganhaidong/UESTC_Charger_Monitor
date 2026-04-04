import requests
import json
from datetime import datetime
import time

# --------------------- 配置部分 ---------------------
# 你给的站点列表，按顺序编号 1~6
STATION_LIST = [
    177972,  # 1
    177970,  # 2
    177968,  # 3
    177983,  # 4
    177975,  # 5
    177977  # 6
]

HEADERS = {
    "sec-ch-ua-platform": "\"Android\"",
    "sec-ch-ua": "\"Chromium\";v=\"142\", \"Android WebView\";v=\"142\", \"Not_A Brand\";v=\"99\"",
    "systemphone": "Android 16",
    "sec-ch-ua-mobile": "?1",
    "brands": "2407FRK8EC",
    "user-agent": "Mozilla/5.0 (Linux; Android 16; 2407FRK8EC Build/BP2A.250605.031.A3; wv) ...",
    "content-type": "application/json;charset=utf-8",
    # "token": "issks_20e1f0ee4d8e087a35b57c5e0bd785c3",  # ← 替换成有效 token
    "accept": "*/*",
    "origin": "https://api.issks.com",
    "x-requested-with": "com.tencent.mm",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://api.issks.com/",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "priority": "u=1, i"
}

PROXIES = {"http": None, "https": None}
TIMEOUT = 10
SLEEP_BETWEEN = 1.5


# --------------------- 主逻辑 ---------------------
def check_station(station_id):
    url = f"https://wemp.issks.com/charge/v1/outlet/station/outlets/{station_id}"

    try:
        resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []

        data = resp.json()
        if data.get("code") != "1":
            return []

        outlets = data.get("data", [])
        free = []

        for outlet in outlets:
            if outlet.get("currentChargingRecordId") == 1:
                free.append({
                    "serial": outlet.get("outletSerialNo"),
                    "outletNo": outlet.get("outletNo")
                })

        return free

    except Exception:
        return []


def main():
    print(f"\n查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("正在查找空闲插座 (currentChargingRecordId == 1)...\n")

    found_any = False

    for idx, sid in enumerate(STATION_LIST, 1):
        free_list = check_station(sid)

        if free_list:
            found_any = True
            print(f"{idx}号站")
            for item in free_list:
                print(f"  空闲序号: {item['serial']:2d}")
            print()

        time.sleep(SLEEP_BETWEEN)

    if not found_any:
        print("所有站点暂无空闲插座")


if __name__ == "__main__":
    main()