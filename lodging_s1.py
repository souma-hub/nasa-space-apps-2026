# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx", "python-dotenv",
#   "pystac-client", "planetary-computer", "odc-stac", "rioxarray",
#   "numpy", "scipy", "matplotlib",
# ]
# ///
"""Sentinel-1 RTC で、水田の倒伏前後の後方散乱の変化を調べる。

1. 春（湛水期）に VV が低く、7 月に植生がある画素を水田とみなす（対象年で判定）
2. 同じ軌道の 12 日ペアで、変化量（dB）を水田の画素ごとに計算する
3. 対象年のイベント期ペアを、(a) 同じ年の平常期ペア、(b) 前年の同じ時期のペア と比べる
   (b) は季節（稲の生育段階）の影響をそろえるための対照

データは Microsoft Planetary Computer の sentinel-1-rtc（認証不要）。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import planetary_computer  # noqa: E402
import pystac_client  # noqa: E402
from odc.stac import load  # noqa: E402
from scipy import stats  # noqa: E402
from scipy.ndimage import uniform_filter  # noqa: E402

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

# (年, 軌道) ごとの比較ペア（12 日間隔、MM-DD）
# 2026: event は 8/11〜14 の大雨・強風をまたぐ。2025: 同じ時期の対照（8/10〜11 に風 12 m/s、雨は少なめ）
PAIRS = {
    (2026, 141): {"baseline": [("07-09", "07-21"), ("07-21", "08-02")],
                  "event": [("08-02", "08-14")], "after": [("08-14", "08-26")]},
    (2026, 39): {"baseline": [("07-26", "08-07")], "event": [("08-07", "08-19")]},
    (2026, 46): {"baseline": [("07-20", "08-01")], "event": [("08-01", "08-13")]},
    (2025, 141): {"baseline": [("07-07", "07-19"), ("07-19", "07-31")],
                  "event": [("07-31", "08-12")], "after": [("08-12", "08-24")]},
    (2025, 39): {"baseline": [("07-24", "08-05")], "event": [("08-05", "08-17")]},
    (2025, 46): {"baseline": [("07-18", "07-30")], "event": [("07-30", "08-11")]},
}
SPRING = ("04-15", "06-10")  # 湛水期（田植え前後）
INDICES = ("VV", "VH", "VH-VV")


def db(x):
    return 10 * np.log10(np.clip(x, 1e-6, None))


def load_db(cat, bbox, orbit, year, res, smooth):
    """軌道の 4〜9 月を読み、平滑化して dB の (vv, vh, 日付 MM-DD) を返す。"""
    items = cat.search(
        collections=["sentinel-1-rtc"], bbox=bbox,
        datetime=f"{year}-04-15/{year}-09-10",
        query={"sat:relative_orbit": {"eq": orbit}},
    ).item_collection()
    ds = load(items, bands=["vv", "vh"], bbox=bbox, crs="EPSG:32654", resolution=res,
              groupby="solar_day", patch_url=planetary_computer.sign, chunks={}).compute()
    out = {}
    for b in ("vv", "vh"):
        v = np.nan_to_num(ds[b].values, nan=0.0)
        if smooth > 1:  # スペックル低減: 線形値で移動平均してから dB にする
            v = uniform_filter(v, size=(1, smooth, smooth))
        out[b] = db(v)
    md = [str(x)[5:10] for x in ds.time.values]
    return out["vv"], out["vh"], md


def paddy_mask(vv, vh, md):
    """春に一度は水面（VV < -17 dB）、7 月は植生（VH > -20 かつ VV > -14 dB）。"""
    md = np.array(md)
    spring = (md >= SPRING[0]) & (md <= SPRING[1])
    july = (md >= "07-01") & (md <= "07-31")
    return ((vv[spring].min(0) < -17) & (vh[july].mean(0) > -20)
            & (vv[july].mean(0) > -14))


def changes(vv, vh, md, pairs):
    """ペアごとに、指標の変化量の 2 次元配列を返す。"""
    idx = {"VV": vv, "VH": vh, "VH-VV": vh - vv}
    res = {}
    for kind, plist in pairs.items():
        for d0, d1 in plist:
            i0, i1 = md.index(d0), md.index(d1)
            res[(kind, d0, d1)] = {n: a[i1] - a[i0] for n, a in idx.items()}
    return res


def summarize(label, res, mask):
    print(f"  {label}")
    print(f"    {'種類':8} {'ペア':13} {'指標':6} {'中央値dB':>8} {'IQR':>6} {'+3dB超':>7} {'-3dB未満':>8}")
    for (kind, d0, d1), row in res.items():
        for n, d in row.items():
            d = d[mask & np.isfinite(d)]
            q1, q2, q3 = np.percentile(d, [25, 50, 75])
            print(f"    {kind:8} {d0}->{d1}  {n:6} {q2:8.2f} {q3 - q1:6.2f}"
                  f" {np.mean(d > 3):7.1%} {np.mean(d < -3):8.1%}")


def main():
    p = argparse.ArgumentParser(description="Sentinel-1 で倒伏の変化を検定")
    p.add_argument("--bbox", type=float, nargs=4, default=[140.15, 35.85, 140.40, 36.0],
                   metavar=("W", "S", "E", "N"))
    p.add_argument("--res", type=int, default=20, help="解像度 m")
    p.add_argument("--year", type=int, default=2026, help="対象年")
    p.add_argument("--control-year", type=int, default=2025, help="対照年")
    p.add_argument("--orbits", type=int, nargs="+", default=[141, 39, 46])
    p.add_argument("--smooth", type=int, default=3, help="平滑化の窓（画素）。1 で無効")
    p.add_argument("--out", default="out")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)

    cat = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    for orbit in a.orbits:
        print(f"== 軌道 {orbit}", flush=True)
        vv, vh, md = load_db(cat, a.bbox, orbit, a.year, a.res, a.smooth)
        mask = paddy_mask(vv, vh, md)
        print(f"  水田画素（{a.year} 判定）: {mask.sum():,} / {mask.size:,}（{mask.mean():.0%}）")
        res = changes(vv, vh, md, PAIRS[(a.year, orbit)])
        summarize(f"{a.year} 年", res, mask)

        cvv, cvh, cmd = load_db(cat, a.bbox, orbit, a.control_year, a.res, a.smooth)
        cres = changes(cvv, cvh, cmd, PAIRS[(a.control_year, orbit)])
        summarize(f"{a.control_year} 年（対照）", cres, mask)

        ev = next(k for k in res if k[0] == "event")
        cev = next(k for k in cres if k[0] == "event")
        base = [k for k in res if k[0] == "baseline"]
        np.save(out / f"mask_{orbit}.npy", mask)
        print("    検定（画素は空間的に相関するので p 値は過小。効果量を主に見る）")
        for n in INDICES:
            e = res[ev][n]
            np.save(out / f"d{n}_{a.year}_{orbit}.npy", np.where(mask, e, np.nan))
            ok = mask & np.isfinite(e) & np.isfinite(cres[cev][n])
            b = np.concatenate([res[k][n][mask & np.isfinite(res[k][n])] for k in base])
            ks = stats.ks_2samp(e[ok], b)
            # 前年との差: 同じ画素で (今年の変化 − 前年の変化)
            did = e[ok] - cres[cev][n][ok]
            np.save(out / f"did{n}_{orbit}.npy", np.where(ok, e - cres[cev][n], np.nan))
            print(f"    {n:6}: 同年平常比 中央値差 {np.median(e[ok]) - np.median(b):+.2f} dB "
                  f"(KS D={ks.statistic:.2f}) / 前年同期比 中央値 {np.median(did):+.2f} dB, "
                  f"+2dB超 {np.mean(did > 2):.0%}, -2dB未満 {np.mean(did < -2):.0%}")
    print("完了。配列は", out)


if __name__ == "__main__":
    main()
