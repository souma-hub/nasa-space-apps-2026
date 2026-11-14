# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pandas", "lxml"]
# ///
"""気象庁「過去の気象データ」から、茨城南部〜千葉北部のアメダス日別値（8〜9 月）を集める。

NASA POWER の風は約 50 km 格子の 1 時間平均で、台風の突風を再現できない
（例: 2019-09-09 の台風 15 号で POWER 6.9 m/s、佐倉の最大瞬間風速 33.9 m/s）。
倒伏の閾値を見るため、地点の最大風速・最大瞬間風速を使う。

出典: 気象庁ホームページ「過去の気象データ検索」。出力は data/amedas_daily.csv。
"""
import argparse
import re
import sys
import time
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import pandas as pd  # noqa: E402

BASE = "https://www.data.jma.go.jp/stats/etrn/view/"
# (都府県番号, 地点番号, 名前, 種類 a=アメダス / s=気象官署)
STATIONS = [
    (40, "1014", "龍ケ崎", "a"), (40, "0911", "江戸崎", "a"), (40, "47646", "つくば", "s"),
    (45, "0376", "我孫子", "a"), (45, "0378", "成田", "a"), (45, "0916", "佐倉", "a"),
    (45, "0375", "香取", "a"),
]
# 表の列位置（daily_a1 / daily_s1）
COLS = {
    "a": {"rain_sum": 1, "rain_1h": 2, "rain_10m": 3, "rh_mean": 7, "ws_mean": 9,
          "ws_max": 10, "gust": 12},
    "s": {"rain_sum": 3, "rain_1h": 4, "rain_10m": 5, "rh_mean": 9, "ws_mean": 11,
          "ws_max": 12, "gust": 14},
}


def num(x):
    """「12.3)」「12.3 ]」のような品質記号を外して数値に。欠測は NaN。"""
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(x))
    return float(m.group(1)) if m else float("nan")


def fetch_month(c, prec, block, kind, year, month):
    url = f"{BASE}daily_{kind}1.php"
    params = {"prec_no": prec, "block_no": block, "year": year, "month": month,
              "day": "", "view": ""}
    for i in range(4):
        try:
            r = c.get(url, params=params)
            r.raise_for_status()
            break
        except httpx.HTTPError as e:
            print(f"  再試行 {i + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** i)
    else:
        return None
    try:
        t = pd.read_html(StringIO(r.text), attrs={"id": "tablefix1"})[0]
    except ValueError:
        return None  # その年はまだ観測がない
    days = t.iloc[:, 0].map(num)
    out = pd.DataFrame({k: t.iloc[:, j].map(num) for k, j in COLS[kind].items()})
    out["date"] = [pd.Timestamp(year, month, int(d)) if d == d else pd.NaT for d in days]
    return out.dropna(subset=["date"])


def main():
    p = argparse.ArgumentParser(description="アメダス日別値を取得")
    p.add_argument("--first-year", type=int, default=2001)
    p.add_argument("--last-year", type=int, default=2026)
    p.add_argument("--out", default="data/amedas_daily.csv")
    a = p.parse_args()
    out = Path(a.out)
    have = pd.read_csv(out, parse_dates=["date"]) if out.exists() else pd.DataFrame()
    frames = [have] if len(have) else []
    with httpx.Client(timeout=60) as c:
        for prec, block, name, kind in STATIONS:
            for y in range(a.first_year, a.last_year + 1):
                for m in (8, 9):
                    if len(have) and ((have.station == name) & (have.date.dt.year == y)
                                      & (have.date.dt.month == m)).any():
                        continue
                    f = fetch_month(c, prec, block, kind, y, m)
                    if f is not None and len(f):
                        f["station"] = name
                        frames.append(f)
                    time.sleep(0.3)  # 気象庁のサーバーに負担をかけない
            print(f"  {name}: 完了", flush=True)
    df = pd.concat(frames).sort_values(["station", "date"])
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    g = df.groupby("station").agg(n=("date", "size"), gust_n=("gust", "count"),
                                  first=("date", "min"))
    print(g.to_string())
    print(f"保存: {out}（{len(df):,} 行）")


if __name__ == "__main__":
    main()
