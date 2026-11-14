# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx", "python-dotenv",
#   "pystac-client", "planetary-computer", "odc-stac", "rioxarray",
#   "numpy", "scipy", "matplotlib", "geopandas", "pyogrio",
# ]
# ///
"""筆ポリゴンの田 1 枚ごとに Sentinel-1 を平均し、倒伏前後の変化を前年同期と比べる。

画素単位（lodging_s1.py）ではスペックルで軌道間の一致が偶然並みだった。
区画の内側（境界から 10 m 内側）の画素を線形値で平均してから dB にすることで、ノイズを減らす。
結果は区画ごとの CSV（data/parcel_<軌道>.csv）に出す。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import planetary_computer  # noqa: E402
import pystac_client  # noqa: E402
from rasterio import features  # noqa: E402

from lodging_s1 import PAIRS, STAC, db, load_db  # noqa: E402


def parcel_means(arr, labels, n):
    """arr (時刻, y, x) の線形値を、区画ラベルごとに平均する → (時刻, 区画)。"""
    lab = labels.ravel()
    ok = lab > 0
    cnt = np.bincount(lab[ok], minlength=n + 1)
    out = np.empty((arr.shape[0], n + 1), dtype="float32")
    for t in range(arr.shape[0]):
        v = arr[t].ravel()
        good = ok & np.isfinite(v) & (v > 0)
        s = np.bincount(lab[good], weights=v[good], minlength=n + 1)
        c = np.bincount(lab[good], minlength=n + 1)
        out[t] = np.where(c >= 0.8 * np.maximum(cnt, 1), s / np.maximum(c, 1), np.nan)
    return out[:, 1:], cnt[1:]


def main():
    p = argparse.ArgumentParser(description="区画平均で倒伏の変化を検定")
    p.add_argument("--bbox", type=float, nargs=4, default=[140.15, 35.85, 140.40, 36.0],
                   metavar=("W", "S", "E", "N"))
    p.add_argument("--fude", default="data/fude_paddy.geojson")
    p.add_argument("--res", type=int, default=10)
    p.add_argument("--inset", type=float, default=10, help="区画を内側に縮める距離 m")
    p.add_argument("--min-px", type=int, default=8, help="使う区画の最小画素数")
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--control-year", type=int, default=2025)
    p.add_argument("--orbits", type=int, nargs="+", default=[141, 39])
    p.add_argument("--out", default="data")
    a = p.parse_args()

    g = gpd.read_file(a.fude).to_crs("EPSG:32654")
    g["geometry"] = g.buffer(-a.inset)
    g = g[~g.is_empty].reset_index(drop=True)
    print(f"区画（{a.inset} m 内側に縮めた後）: {len(g):,}")

    cat = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    tables = {}
    for orbit in a.orbits:
        print(f"== 軌道 {orbit}", flush=True)
        rows = {"OBJECTID": g["OBJECTID"].values}
        for year in (a.year, a.control_year):
            vv, vh, md, gbox = load_db(cat, a.bbox, orbit, year, a.res, smooth=0)
            labels = features.rasterize(
                ((geom, i + 1) for i, geom in enumerate(g.geometry)),
                out_shape=gbox.shape, transform=gbox.affine, fill=0, dtype="int32")
            mvv, cnt = parcel_means(vv, labels, len(g))
            mvh, _ = parcel_means(vh, labels, len(g))
            rows["npx"] = cnt
            for kind, plist in PAIRS[(year, orbit)].items():
                for d0, d1 in plist:
                    i0, i1 = md.index(d0), md.index(d1)
                    tag = f"{year}_{kind}_{d0}_{d1}"
                    rows[f"dVV_{tag}"] = db(mvv[i1]) - db(mvv[i0])
                    rows[f"dVH_{tag}"] = db(mvh[i1]) - db(mvh[i0])
                    rows[f"dRatio_{tag}"] = rows[f"dVH_{tag}"] - rows[f"dVV_{tag}"]
        t = pd.DataFrame(rows)
        t = t[t.npx >= a.min_px]
        ev = next(c for c in t if c.startswith(f"dVH_{a.year}_event"))[4:]
        cev = next(c for c in t if c.startswith(f"dVH_{a.control_year}_event"))[4:]
        for n in ("VV", "VH", "Ratio"):
            t[f"did{n}"] = t[f"d{n}_{ev}"] - t[f"d{n}_{cev}"]
        t.to_csv(Path(a.out) / f"parcel_{orbit}.csv", index=False)
        tables[orbit] = t.set_index("OBJECTID")
        print(f"  使った区画: {len(t):,}（{a.min_px} 画素以上）")
        for n in ("VV", "VH", "Ratio"):
            d = t[f"did{n}"].dropna()
            print(f"  前年同期比 d{n}: 中央値 {d.median():+.2f} dB, IQR {d.quantile(.75) - d.quantile(.25):.2f},"
                  f" -2dB未満 {np.mean(d < -2):.1%}, +2dB超 {np.mean(d > 2):.1%}")

    if len(tables) >= 2:
        o1, o2 = list(tables)[:2]
        j = tables[o1].join(tables[o2], how="inner", lsuffix=f"_{o1}", rsuffix=f"_{o2}")
        print(f"== 軌道 {o1} と {o2} の一致（区画 {len(j):,}）")
        for n in ("VV", "VH", "Ratio"):
            x, y = j[f"did{n}_{o1}"], j[f"did{n}_{o2}"]
            ok = x.notna() & y.notna()
            r = np.corrcoef(x[ok], y[ok])[0, 1]
            both = np.mean((x[ok] < -2) & (y[ok] < -2))
            exp = np.mean(x[ok] < -2) * np.mean(y[ok] < -2)
            print(f"  did{n}: 相関 r={r:.2f}, 両方で -2dB未満 {both:.1%}（独立なら {exp:.1%}）")


if __name__ == "__main__":
    main()
