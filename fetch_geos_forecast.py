# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas"]
# ///
"""NASA GEOS-FP の予報から、茨城南部〜千葉北部の 1 時間ごとの雨と 10 m 風速を取り出す。

GEOS-FP は NASA GMAO の全球予報モデル（約 0.3°×0.25°）。00 時の回は 10 日先まで、ほかの回は短い。
NCCS の OPeNDAP（GrADS DODS）から、範囲だけを ASCII で取る。認証は要らない。
学習に使う NASA POWER（MERRA-2）と同じ GEOS 系のモデルなので、癖（突風の過小評価など）がそろう。
出力は data/geos_forecast_<回>.csv（time_utc, time_jst, rain_mm_h, rain_max_mm_h, ws10m, ws10m_max）。
"""
import argparse
import re
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BASE = "https://opendap.nccs.nasa.gov/dods/GEOS-5/fp/0.25_deg/fcast"
# 格子: lat = -90 + 0.25 j, lon = -180 + 0.3125 i
LAT = (503, 505)    # 35.75〜36.25N
LON = (1023, 1026)  # 139.69〜140.63E
CHUNK = 48


def latest_cycle(c, hour=None):
    r = c.get(f"{BASE}/tavg1_2d_flx_Nx/")
    cycles = sorted(set(re.findall(r"tavg1_2d_flx_Nx\.(\d{8}_\d{2})", r.text)))
    if hour is not None:
        cycles = [x for x in cycles if x.endswith(f"_{hour:02d}")]
    return cycles[-1]


def grab(c, coll, cycle, var):
    """変数を (時刻, lat, lon) の配列で取る。"""
    u = f"{BASE}/{coll}/{coll}.{cycle}"
    das = c.get(f"{u}.das").text
    n = int(re.search(r'time \{.*?grads_size "(\d+)"', das, re.S).group(1))
    t0 = re.search(r'time \{.*?grads_min "([^"]+)"', das, re.S).group(1)
    ny, nx = LAT[1] - LAT[0] + 1, LON[1] - LON[0] + 1
    parts = []
    for s in range(0, n, CHUNK):  # サーバーが重いと 504 になるので、48 時間ずつ取って再試行する
        e = min(s + CHUNK, n) - 1
        q = f"{var}[{s}:{e}][{LAT[0]}:{LAT[1]}][{LON[0]}:{LON[1]}]"
        for i in range(6):
            r = c.get(f"{u}.ascii?{q.replace('[', '%5B').replace(']', '%5D')}")
            vals = [float(x) for line in r.text.splitlines()
                    if line.startswith("[") and "]," in line for x in line.split(",")[1:]]
            if r.status_code == 200 and len(vals) == (e - s + 1) * ny * nx:
                break
            print(f"  {coll} {var} {s}-{e} 再試行 {i + 1}: HTTP {r.status_code}", file=sys.stderr)
            time.sleep(2 ** i)
        else:
            sys.exit(f"{coll} {var} を取得できませんでした")
        parts.append(np.array(vals).reshape(e - s + 1, ny, nx))
    a = np.concatenate(parts)
    a[a > 1e14] = np.nan
    start = pd.to_datetime(t0, format="%H:%Mz%d%b%Y")
    return pd.date_range(start, periods=n, freq="h"), a


def main():
    p = argparse.ArgumentParser(description="GEOS-FP の予報を範囲で取得")
    p.add_argument("--cycle", help="YYYYMMDD_HH（省略時は最新の 00 時の回）")
    p.add_argument("--out", default="data")
    a = p.parse_args()
    with httpx.Client(timeout=300) as c:
        cycle = a.cycle or latest_cycle(c, hour=0)
        print(f"予報の回: {cycle}（世界時）", flush=True)
        t, pr = grab(c, "tavg1_2d_flx_Nx", cycle, "prectot")   # kg m-2 s-1
        t2, u = grab(c, "tavg1_2d_slv_Nx", cycle, "u10m")
        _, v = grab(c, "tavg1_2d_slv_Nx", cycle, "v10m")
    pr = pr * 3600  # mm/h
    ws = np.hypot(u, v)
    n = min(len(t), len(t2))
    df = pd.DataFrame({
        "time_utc": t[:n], "rain_mm_h": np.nanmean(pr[:n], axis=(1, 2)),
        "rain_max_mm_h": np.nanmax(pr[:n], axis=(1, 2)),
        "ws10m": np.nanmean(ws[:n], axis=(1, 2)), "ws10m_max": np.nanmax(ws[:n], axis=(1, 2)),
    })
    df["time_jst"] = df.time_utc + pd.Timedelta(hours=9)
    out = Path(a.out) / f"geos_forecast_{cycle}.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    d = df.set_index("time_jst").resample("D").agg(
        {"rain_mm_h": "sum", "rain_max_mm_h": "max", "ws10m_max": "max"})
    print(d.rename(columns={"rain_mm_h": "雨 mm/日", "rain_max_mm_h": "最大1時間 mm",
                            "ws10m_max": "最大風速 m/s"}).round(1).to_string())
    print(f"保存: {out}（{len(df)} 時間）")


if __name__ == "__main__":
    main()
