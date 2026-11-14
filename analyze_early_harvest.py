# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""しなくてよい早刈りを、NASA のデータでどれだけ減らせたかを過去の台風で数える。

前提（ヒアリング）: 台風の予報・警報が出たら、予定より早くても安全側で刈り取る。
- 「警報が出た状況」の代わりに、8〜9 月に関東南部（35.9N, 140.2E）から 300 km 以内に近づいた台風を使う
- 結果は、農水省の災害統計（茨城＋千葉の水稲被害面積）。100 ha 以上を「被害あり」とする
- 判断に使うのは NASA のデータだけ: IMERG の雨、POWER の風（MERRA-2）・土壌水分、POWER の気温から推定した実り具合
- 規則「雨が R mm 以上 かつ 稲が実っている（コシヒカリ出穂後 G℃ 以上）なら刈る」を、
  被害ありの台風を 1 つも見逃さない範囲で、刈る回数が最も少なくなるように選ぶ（安全側）
アメダスの最大瞬間風速は、表示用（地上検証）にだけ載せる。
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analyze_disasters import best_track  # noqa: E402

NEAR_KM = 300
DAMAGE_HA = 100
Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def fit_rule(tb):
    """被害ありを 1 つも見逃さない中で、刈る回数が最少の (雨 R, 出穂後積算 G)。同点なら閾値が低い方（安全側）。"""
    best = None
    for R, G in itertools.product(range(0, 301, 10), range(0, 1201, 50)):
        harvest = (tb["雨IMERG"] >= R) & (tb["コシ出穂後"].fillna(9999) >= G)
        if (tb["被害あり"] & ~harvest).any():
            continue
        cand = (int(harvest.sum()), R, G)
        if best is None or cand < best[0]:
            best = (cand, R, G, harvest)
    return best[1], best[2], best[3]


def main():
    bst = best_track()
    dd = pd.read_csv("data/disaster_damage.csv")
    years = sorted(dd.year.unique())
    dd["rice"] = np.where(dd.listed & dd.table_has_rice, dd.rice_area_ha.fillna(0), 0.0)
    dd["nums"] = dd.disaster.str.translate(Z2H).str.findall(r"(?:台風)?第(\d+)号")
    dmg = {}
    for r in dd.itertuples():
        for n in r.nums:
            k = (r.year, int(n))
            dmg[k] = dmg.get(k, {})
            dmg[k][r.pref] = max(dmg[k].get(r.pref, 0.0), r.rice)
    ds = pd.read_csv("data/dataset.csv", parse_dates=["date"]).set_index("date")

    t = bst[(bst.km <= NEAR_KM) & bst.jst.dt.month.isin([8, 9]) & bst.year.isin(years)].copy()
    rows = []
    for r in t.itertuples():
        d = r.jst.normalize()
        w = ds.loc[d - pd.Timedelta(days=2): d + pd.Timedelta(days=1)]
        if not len(w):
            continue
        rows.append({
            "台風": f"{r.year} 第{r.num}号", "最接近": d.date(), "距離km": round(r.km),
            "雨IMERG": w.imerg_mean.sum(), "雨POWER": w.rain_sum.sum(),
            "風POWER": w.ws_max.max(),
            "コシ出穂後": ds.loc[d, "gdd_koshihikari"] if d in ds.index else np.nan,
            "瞬間風速(地上)": w.am_gust_max.max(),
            "被害ha": sum(dmg.get((r.year, r.num), {}).values()),
        })
    tb = pd.DataFrame(rows).sort_values("最接近")
    tb["被害あり"] = tb["被害ha"] >= DAMAGE_HA
    n, npos = len(tb), int(tb["被害あり"].sum())
    print(f"{years[0]}〜{years[-1]} 年の 8〜9 月に {NEAR_KM} km 以内に来た台風: {n} 個"
          f"（水稲被害 {DAMAGE_HA} ha 以上: {npos} 個 / それ以外: {n - npos} 個）")
    print("今のやり方（警報が出たら全部刈る）なら、早刈り {} 回のうち {} 回は被害が出なかった台風\n".format(n, n - npos))
    print(tb.to_string(index=False, float_format="%.0f"))

    R, G, harvest = fit_rule(tb)
    print(f"\n== 安全側の規則（被害ありの見逃し 0）: IMERG の雨が {R} mm 以上 かつ コシヒカリ出穂後 {G}℃ 以上なら刈る")
    print(f"  刈る回数: {int(harvest.sum())} / {n}（減らせた早刈り: {n - int(harvest.sum())} 回、"
          f"被害なしの台風 {n - npos} 個のうち {int((~harvest & ~tb['被害あり']).sum())} 個で『待ってよい』）")
    print("  注意: 台風の数が少なく、規則は過去に合わせ込んだもの（未来の性能は 1 年抜きの検証で見る必要がある）")
    # 1 つの台風を抜いて規則を決め、抜いた台風に当てる（過去への合わせ込みを除いた性能）
    pred = []
    for i in range(n):
        rest = tb.drop(tb.index[i])
        r_, g_, _ = fit_rule(rest)
        row = tb.iloc[i]
        pred.append(bool(row["雨IMERG"] >= r_ and (row["コシ出穂後"] if row["コシ出穂後"] == row["コシ出穂後"] else 9999) >= g_))
    pred = np.array(pred)
    miss = int((tb["被害あり"].values & ~pred).sum())
    skip = int((~tb["被害あり"].values & ~pred).sum())
    print(f"\n== 1 つ抜きの検証: 見逃し {miss} / {npos}、『待ってよい』と言えた被害なしの台風 {skip} / {n - npos}")
    tb.assign(刈る=harvest, 刈る_1つ抜き=pred).to_csv("results/early_harvest_typhoons.csv", index=False)


if __name__ == "__main__":
    main()
