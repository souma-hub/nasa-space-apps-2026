# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "xarray", "netcdf4", "scikit-learn"]
# ///
"""台風・大雨のときに「刈る／待ってよい」を出す（茨城南部〜千葉北部）。入力はすべて NASA のデータ。
判断は統一モデル（lodging_unified.py: 全国の雨＋風＋県の補正 ＋ 茨城・千葉の実り具合）で出す。

使い方:
  uv run predict_lodging.py --variety koshihikari            # 今の予報で判断（GEOS-FP の最新の 00 時の回）
  uv run predict_lodging.py --pref 千葉 --replay 2019-09-09   # 県を選ぶ（茨城か千葉）
  uv run predict_lodging.py --replay 2019-09-09              # 過去の台風を再現（予報の代わりに IMERG の実測を使う）
  uv run predict_lodging.py --replay 2016-08-22 --variety nijinokirameki

- 過去 2 日の雨: GPM IMERG（再現は data/imerg_daily.csv、今の判断は OPeNDAP の速報版）
- これから 2 日の雨と風: GEOS-FP の予報（再現では IMERG の雨・POWER の風の実測で代用＝予報が完璧だった場合）
- 稲の実り具合: NASA POWER の気温 → phenology.py（品種別の出穂後積算気温）
Earthdata のトークンは、クラウド環境ではプロキシが opendap.earthdata.nasa.gov 宛てに自動で付ける。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from lodging_unified import VARIETY_JA, decide  # noqa: E402
from phenology import stage_features  # noqa: E402

LAT, LON = 35.90, 140.20
POWER_DAILY = "https://power.larc.nasa.gov/api/temporal/daily/point"


def power_t2m(year, until):
    r = httpx.get(POWER_DAILY, params={"parameters": "T2M", "community": "AG", "latitude": LAT,
                                       "longitude": LON, "start": f"{year}0501",
                                       "end": until.strftime("%Y%m%d"), "format": "JSON"}, timeout=120)
    r.raise_for_status()
    t = pd.Series(r.json()["properties"]["parameter"]["T2M"])
    t.index = pd.to_datetime(t.index, format="%Y%m%d")
    return t.replace(-999.0, np.nan).dropna()


def gdd_on(day, variety):
    """その日の品種別の出穂後積算気温。足りない日は平年並み（過去の同じ日の平均）で埋める。"""
    t = power_t2m(day.year, min(day, pd.Timestamp.today().normalize()))
    full = pd.date_range(f"{day.year}-05-01", f"{day.year}-09-30")
    hist = pd.read_csv("data/power_daily_t2m.csv", parse_dates=["date"]).set_index("date")["T2M"]
    clim = hist.groupby(hist.index.strftime("%m-%d")).mean()
    t = t.reindex(full).fillna(pd.Series(clim.reindex(full.strftime("%m-%d")).values, index=full))
    st = stage_features(t)
    if day > full[-1]:
        return float(st[f"gdd_{variety}"].iloc[-1]) + 20 * (day - full[-1]).days  # 10 月以降は概算
    return float(st.loc[day, f"gdd_{variety}"])


def replay(day, variety):
    im = pd.read_csv("data/imerg_daily.csv", parse_dates=["date"]).set_index("date").imerg_mean
    past = im.loc[day - pd.Timedelta(days=2): day - pd.Timedelta(days=1)].sum()
    fcst = im.loc[day: day + pd.Timedelta(days=1)].sum()
    ds = pd.read_csv("data/dataset.csv", parse_dates=["date"]).set_index("date")
    wind = float(ds.loc[day - pd.Timedelta(days=2): day + pd.Timedelta(days=1), "ws_max"].max())
    return past, fcst, wind, float(ds.loc[day, f"gdd_{variety}"])


def live(variety):
    import fetch_geos_forecast as g
    import fetch_imerg as fi
    with httpx.Client(timeout=300, follow_redirects=True) as c:
        cycle = g.latest_cycle(c, hour=0)
        t, pr = g.grab(c, "tavg1_2d_flx_Nx", cycle, "prectot")
        now = pd.Timestamp.now('UTC').tz_localize(None)
        m = (t >= now) & (t < now + pd.Timedelta(days=2))
        fcst = float(np.nanmean(pr[m] * 3600, axis=(1, 2)).sum())
        tw, u = g.grab(c, "tavg1_2d_slv_Nx", cycle, "u10m")
        _, v = g.grab(c, "tavg1_2d_slv_Nx", cycle, "v10m")
        mw = (tw >= now) & (tw < now + pd.Timedelta(days=2))
        wind = float(np.nanmean(np.hypot(u, v)[mw], axis=(1, 2)).max())
        today = (now + pd.Timedelta(hours=9)).normalize()
        s, e = (today - pd.Timedelta(days=4)).date(), (today - pd.Timedelta(days=1)).date()
        urls = fi.opendap_urls(c, fi.LATE, s, e)
        past = sum(r["imerg_mean"] for d, u in sorted(urls.items())[-2:]
                   if (r := fi.fetch_one(c, d, u, "late")))
    print(f"GEOS-FP の予報: {cycle}（世界時）、これから 48 時間の雨 {fcst:.1f} mm")
    print(f"GEOS-FP の予報: これから 48 時間の最大風速 {wind:.1f} m/s")
    print(f"IMERG 速報版: 直近 2 日の雨 {past:.1f} mm（最新 {max(urls) if urls else 'なし'}）")
    return past, fcst, wind, gdd_on(today, variety), today


def main():
    p = argparse.ArgumentParser(description="台風・大雨のときの刈り取り判断")
    p.add_argument("--variety", default="koshihikari", choices=list(VARIETY_JA))
    p.add_argument("--pref", default="茨城", choices=["茨城", "千葉"])
    p.add_argument("--replay", help="過去の日付 YYYY-MM-DD を再現する")
    a = p.parse_args()
    if a.replay:
        day = pd.Timestamp(a.replay)
        past, fcst, wind, gdd = replay(day, a.variety)
        res = decide(a.pref, past + fcst, 0, wind, gdd, a.variety)  # 再現は実測なので予報の余裕を掛けない
        print(f"再現: {day.date()}（予報の代わりに IMERG の実測を使用）")
    else:
        past, fcst, wind, gdd, day = live(a.variety)
        res = decide(a.pref, past, fcst, wind, gdd, a.variety)
    print(f"県: {a.pref}、品種: {VARIETY_JA[a.variety]}")
    print(f"判断: 【{res['decision']}】 被害が出る確率の目安 {res['probability']:.0%}")
    for r in res["reasons"]:
        print(f"  - {r}")
    print("  ※ 支援の道具であり、最終判断は農家と地元の専門家が行う")


if __name__ == "__main__":
    main()
