# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pandas", "numpy", "xarray", "netcdf4"]
# ///
"""NASA GPM IMERG（日別、0.1°）を、茨城南部〜千葉北部の範囲だけ OPeNDAP で切り出して集める。

NASA POWER（約 0.5°）より細かい雨を、地域平均と範囲内の最大で持つ。
- 2025-09-30 までは確定版 Final（GPM_3IMERGDF）、それ以降は速報版 Late（GPM_3IMERGDL）
- 認証: Earthdata Login のトークン。クラウド環境では opendap.earthdata.nasa.gov 宛ての通信に
  プロキシが自動で付ける（コードにトークンは書かない）
出力は data/imerg_daily.csv（date, imerg_mean, imerg_max, product）。
"""
import argparse
import io
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
FINAL = ("C2723754864-GES_DISC", "2025-09-30")  # 確定版はここまで
LATE = "C2723754859-GES_DISC"
# 0.1° 格子の添字: lon = -179.95 + 0.1 i, lat = -89.95 + 0.1 j
LON = (3199, 3204)  # 139.95〜140.45E
LAT = (1257, 1260)  # 35.75〜36.05N
CE = (f"dap4.ce=/precipitation[0:1:0][{LON[0]}:1:{LON[1]}][{LAT[0]}:1:{LAT[1]}]"
      .replace("[", "%5B").replace("]", "%5D"))


def opendap_urls(c, concept, start, end):
    """CMR から、期間内の日別グラニュールの OPeNDAP URL を {日付: URL} で返す。"""
    out, page = {}, 1
    while True:
        r = c.get(CMR, params={"collection_concept_id": concept, "page_size": 200,
                               "page_num": page, "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z"})
        e = r.json()["feed"]["entry"]
        for g in e:
            u = next((lk["href"] for lk in g["links"]
                      if "opendap.earthdata.nasa.gov" in lk.get("href", "")), None)
            if u:
                out[g["time_start"][:10]] = u
        if len(e) < 200:
            return out
        page += 1


def fetch_one(c, day, url, product):
    for i in range(4):
        try:
            r = c.get(f"{url}.dap.nc4?{CE}")
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".nc4") as f:
                f.write(r.content)
                f.flush()
                d = xr.open_dataset(f.name)
                v = d["precipitation"].values.astype("float64")
                units = d["precipitation"].attrs.get("units", "")
                d.close()
            v[v < 0] = np.nan
            if "hr" in units:  # 日別でも単位が mm/hr（1 日の平均強度）の場合は mm/day に直す
                v = v * 24
            return {"date": day, "imerg_mean": np.nanmean(v), "imerg_max": np.nanmax(v),
                    "product": product, "units": units}
        except Exception as e:
            print(f"  {day} 再試行 {i + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** i)
    return None


def main():
    p = argparse.ArgumentParser(description="GPM IMERG 日別を範囲で切り出す")
    p.add_argument("--first-year", type=int, default=2001)
    p.add_argument("--last-year", type=int, default=2026)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="data/imerg_daily.csv")
    a = p.parse_args()
    out = Path(a.out)
    have = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["date"])
    done = set(have["date"])

    with httpx.Client(timeout=120, follow_redirects=True) as c:
        jobs = []
        for y in range(a.first_year, a.last_year + 1):
            s, e = f"{y}-08-01", f"{y}-09-30"
            if e <= FINAL[1]:
                urls, prod = opendap_urls(c, FINAL[0], s, e), "final"
            else:
                urls, prod = opendap_urls(c, LATE, s, e), "late"
            jobs += [(d, u, prod) for d, u in urls.items() if d not in done]
        print(f"取得する日: {len(jobs)}", flush=True)
        rows = have.to_dict("records")
        with ThreadPoolExecutor(a.workers) as ex:
            for n, res in enumerate(ex.map(lambda j: fetch_one(c, *j), jobs), 1):
                if res:
                    rows.append(res)
                if n % 100 == 0:
                    print(f"  {n} / {len(jobs)}", flush=True)
                    pd.DataFrame(rows).sort_values("date").to_csv(out, index=False)
    out.parent.mkdir(exist_ok=True)
    df = pd.DataFrame(rows).sort_values("date")
    df.to_csv(out, index=False)
    print(f"保存: {out}（{len(df):,} 日、単位 {sorted(set(df.get('units', pd.Series(dtype=str)).dropna()))}）")


if __name__ == "__main__":
    main()
