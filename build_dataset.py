# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas"]
# ///
"""NASA POWER の時間値と events.csv から、倒伏の学習用データを作る。

単位は「地域 × 日（JST）」。対象は稲の出穂〜収穫期にあたる 8〜9 月、2001 年〜。
- data/power_<地域>.csv: 時間値のキャッシュ
- data/dataset.csv: 日ごとの特徴量とラベル（統計検定・ロジスティック回帰用）
- data/sequences.npz: 各日の終わりまでの 72 時間の時系列（RNN 用）

ラベル: events.csv の期間に入る日を 1、それ以外を 0。
注意: 0 は「倒伏の報告が見つかっていない」であり、「倒伏がなかった」とは限らない。
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

POWER = "https://power.larc.nasa.gov/api/temporal/hourly/point"
PARAMS = ["WS10M", "WS2M", "WD10M", "PRECTOTCORR", "RH2M", "T2M"]
# 地域の代表点。POWER（MERRA-2）は約 0.5°×0.625° の格子で、茨城南部と千葉北部は同じ格子に入る
# （両方を別地域にすると同じ日を 2 回数えてしまう）ので、1 地域にまとめる
REGIONS = {"kanto_se": (35.90, 140.20)}  # 茨城南部〜千葉北部（稲敷・龍ケ崎・印西・成田）
REGION_OF = {"ibaraki_south": "kanto_se", "chiba_north": "kanto_se"}  # events.csv の region → 格子
SEASON = ("08-01", "09-30")
SEQ_HOURS = 72
SEQ_COLS = ["WS10M", "WS2M", "PRECTOTCORR", "RH2M", "T2M", "WD_sin", "WD_cos"]


def fetch_region(name, lat, lon, years, cache):
    if cache.exists():
        df = pd.read_csv(cache, parse_dates=["time"])
        have = set(df.time.dt.year)
        if set(years) <= have:
            return df
    frames = []
    with httpx.Client(timeout=120) as c:
        for y in years:
            # 72 時間の窓のため、季節の 3 日前から取る
            params = {"parameters": ",".join(PARAMS), "community": "AG", "latitude": lat,
                      "longitude": lon, "start": f"{y}0729", "end": f"{y}0930",
                      "format": "JSON", "time-standard": "LST"}
            for i in range(4):
                try:
                    r = c.get(POWER, params=params)
                    r.raise_for_status()
                    p = r.json()["properties"]["parameter"]
                    break
                except (httpx.HTTPError, KeyError) as e:
                    print(f"  {name} {y} 再試行 {i + 1}: {e}", file=sys.stderr)
                    time.sleep(2 ** i)
            else:
                sys.exit(f"{name} {y} の取得に失敗しました")
            f = pd.DataFrame(p)
            f.index = pd.to_datetime(f.index, format="%Y%m%d%H")
            frames.append(f)
            print(f"  {name} {y}: {len(f)} 時間", flush=True)
    df = pd.concat(frames).rename_axis("time").reset_index()
    df = df.replace(-999.0, np.nan)
    df.to_csv(cache, index=False)
    return df


def daily_features(h):
    """時間値（1 地域）から日ごとの特徴量を作る。"""
    h = h.set_index("time").sort_index()
    ws, rain = h["WS10M"], h["PRECTOTCORR"].clip(lower=0)
    d = pd.DataFrame({
        "ws_max": ws.resample("D").max(),
        "ws_mean": ws.resample("D").mean(),
        "ws2_max": h["WS2M"].resample("D").max(),
        "hours_ws_ge6": (ws >= 6).resample("D").sum(),
        "hours_ws_ge8": (ws >= 8).resample("D").sum(),
        "rain_sum": rain.resample("D").sum(),
        "rain_max_1h": rain.resample("D").max(),
        "hours_rain_ge1": (rain >= 1).resample("D").sum(),
        # 風と雨が同時: 風速 6 m/s 以上の時間に降った雨の量（濡れて重い稲に風）
        "rain_while_windy": (rain * (ws >= 6)).resample("D").sum(),
        "rh_mean": h["RH2M"].resample("D").mean(),
    })
    # 前の日からの積み上げ（土が緩む・稲が濡れて重くなる）
    d["rain_72h"] = d["rain_sum"].rolling(3, min_periods=1).sum()
    d["ws_max_72h"] = d["ws_max"].rolling(3, min_periods=1).max()
    d["doy"] = d.index.day_of_year  # 生育段階の代わり（出穂からの日数の近似）
    return d


def sequences(h, days):
    """各日の 24 時までの 72 時間の時系列 → (日数, 72, 特徴数)。"""
    h = h.set_index("time").sort_index().copy()
    wd = np.deg2rad(h["WD10M"])
    h["WD_sin"], h["WD_cos"] = np.sin(wd), np.cos(wd)
    h["PRECTOTCORR"] = h["PRECTOTCORR"].clip(lower=0)
    x = h[SEQ_COLS]
    out = np.full((len(days), SEQ_HOURS, len(SEQ_COLS)), np.nan, dtype="float32")
    for i, day in enumerate(days):
        end = day + pd.Timedelta(hours=23)
        w = x.loc[end - pd.Timedelta(hours=SEQ_HOURS - 1):end]
        if len(w) == SEQ_HOURS:
            out[i] = w.values
    return out


def main():
    p = argparse.ArgumentParser(description="倒伏の学習用データを作る")
    p.add_argument("--first-year", type=int, default=2001)
    p.add_argument("--last-year", type=int, default=2026)
    p.add_argument("--events", default="events.csv")
    p.add_argument("--out", default="data")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    years = list(range(a.first_year, a.last_year + 1))
    ev = pd.read_csv(a.events, parse_dates=["start", "end"])
    ev["region"] = ev["region"].map(REGION_OF).fillna(ev["region"])
    # 同じ格子の同じ期間は 1 つにまとめ、確度は高い方を採る
    rank = {"high": 0, "medium": 1, "low": 2}
    ev = (ev.assign(_r=ev.confidence.map(rank)).sort_values("_r")
            .drop_duplicates(["start", "end", "region"]).drop(columns="_r"))

    rows, seqs = [], []
    for name, (lat, lon) in REGIONS.items():
        h = fetch_region(name, lat, lon, years, out / f"power_{name}.csv")
        d = daily_features(h)
        md = d.index.strftime("%m-%d")
        d = d[(md >= SEASON[0]) & (md <= SEASON[1])].copy()
        d["region"], d["label"], d["confidence"], d["cause"] = name, 0, "", ""
        for e in ev[ev.region == name].itertuples():
            m = (d.index >= e.start) & (d.index <= e.end)
            d.loc[m, ["label", "confidence", "cause"]] = [1, e.confidence, e.cause]
        rows.append(d)
        seqs.append(sequences(h, d.index))
    ds = pd.concat(rows).rename_axis("date").reset_index()
    ds.to_csv(out / "dataset.csv", index=False)
    x = np.concatenate(seqs)
    np.savez_compressed(out / "sequences.npz", x=x, y=ds["label"].values,
                        date=ds["date"].astype(str).values, region=ds["region"].values,
                        cols=np.array(SEQ_COLS))
    print(f"保存: {out / 'dataset.csv'}（{len(ds):,} 行、倒伏あり {ds.label.sum()} 日）")
    print(f"保存: {out / 'sequences.npz'}（{x.shape}）")


if __name__ == "__main__":
    main()
