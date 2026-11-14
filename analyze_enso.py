# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""エルニーニョ・ラニーニャ（ONI）と、関東南部の倒伏リスクの年ごとの多さに関係があるかを検定する。

年ごとの危険度（8〜9 月）:
- n_typhoon: 関東南部（35.9N, 140.2E）から 300 km 以内に来た台風の数（気象庁ベストトラック、1951 年〜）
- n_risky: そのうち、倒伏の条件に当たった台風の数（1981 年〜、NASA POWER）
  条件は analyze_early_harvest.py の規則と同じ考え方: 前後 4 日の雨 30 mm 以上 かつ コシヒカリ出穂後 400℃ 以上
  （規則の雨は IMERG で決めたが、1981 年までさかのぼるため POWER の雨を使う）
ONI（NOAA CPC）: 田植え前に分かる春（MAM）と、その夏（JJA）。
検定: Spearman の順位相関、エルニーニョ（ONI ≥ 0.5）／平常／ラニーニャ（≤ −0.5）の Kruskal-Wallis。
4 つ検定するので Bonferroni 補正後の有意水準は 0.0125。おまけに n_risky の年トレンド（Kendall）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from analyze_disasters import best_track  # noqa: E402
from phenology import stage_features  # noqa: E402

NEAR_KM, RAIN_MM, GDD = 300, 30, 400


def load_oni(path="data/oni.ascii.txt"):
    o = pd.read_csv(path, sep=r"\s+")
    return o.pivot(index="YR", columns="SEAS", values="ANOM")


def main():
    bst = best_track()
    t = bst[(bst.km <= NEAR_KM) & bst.jst.dt.month.isin([8, 9])].copy()
    t["date"] = t.jst.dt.normalize()

    p = pd.read_csv("data/power_daily_1981.csv", skiprows=10)
    p["date"] = pd.to_datetime(p.YEAR.astype(str), format="%Y") + pd.to_timedelta(p.DOY - 1, "D")
    p = p.set_index("date").replace(-999.0, np.nan)
    t2m = p.T2M[(p.index.month >= 5) & (p.index.month <= 9)].interpolate()
    st = stage_features(t2m)

    risky = []
    for r in t.itertuples():
        if r.date.year < 1981:
            risky.append(np.nan)
            continue
        rain = p.PRECTOTCORR.loc[r.date - pd.Timedelta(days=2): r.date + pd.Timedelta(days=1)].sum()
        g = st.gdd_koshihikari.get(r.date, np.nan)
        risky.append(float(rain >= RAIN_MM and g == g and g >= GDD))
    t["risky"] = risky

    years = range(1951, 2027)
    y = pd.DataFrame(index=years)
    y["n_typhoon"] = t.groupby(t.date.dt.year).size().reindex(years, fill_value=0)
    y["n_risky"] = t.groupby(t.date.dt.year).risky.sum(min_count=1).reindex(years)
    y.loc[y.index >= 1981, "n_risky"] = y.loc[y.index >= 1981, "n_risky"].fillna(0)
    oni = load_oni()
    y["oni_mam"], y["oni_jja"] = oni["MAM"].reindex(years), oni["JJA"].reindex(years)
    y.rename_axis("year").to_csv("results/enso_years.csv")

    print(f"8〜9 月に {NEAR_KM} km 以内に来た台風: 1951〜2026 年で {len(t)} 個"
          f"（倒伏の条件に当たったもの: 1981 年〜で {int(np.nansum(t.risky))} 個）\n")
    print("== エルニーニョ・ラニーニャとの関係（Bonferroni 補正後の有意水準 0.0125）")
    for col, label, span in (("n_typhoon", "近づいた台風の数", "1951〜"),
                             ("n_risky", "倒伏の条件に当たった台風の数", "1981〜")):
        for o, ol in (("oni_mam", "春 MAM（田植え前に分かる）"), ("oni_jja", "夏 JJA")):
            d = y[[col, o]].dropna()
            rho = stats.spearmanr(d[o], d[col])
            ph = pd.cut(d[o], [-9, -0.5, 0.5, 9], labels=["ラニーニャ", "平常", "エルニーニョ"])
            groups = [d[col][ph == k] for k in ["ラニーニャ", "平常", "エルニーニョ"]]
            kw = stats.kruskal(*groups)
            means = " / ".join(f"{k} {g.mean():.2f}（{len(g)}年）"
                               for k, g in zip(["ラニーニャ", "平常", "エルニーニョ"], groups))
            print(f"  {label}（{span}）× {ol}: ρ={rho.statistic:+.2f} p={rho.pvalue:.3f} / "
                  f"Kruskal p={kw.pvalue:.3f}\n      年平均: {means}")
    d = y.n_risky.dropna()
    tau = stats.kendalltau(d.index, d.values)
    print(f"\n== おまけ: 倒伏の条件に当たった台風の数の年トレンド（1981〜2026、Kendall）: τ={tau.statistic:+.2f} p={tau.pvalue:.3f}")


if __name__ == "__main__":
    main()
