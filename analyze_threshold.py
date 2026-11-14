# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""data/dataset.csv で、倒伏ありの日と報告なしの日の気象を比べ、閾値を探す。

1. 特徴量ごとに Mann-Whitney U 検定（倒伏あり vs 報告なし）と効果量（順位相関 r）
2. イベント単位（期間内の最大値）で、各イベントが報告なしの日の中で何パーセンタイルにあたるか
3. 「風雨が強かったのに報告がない日」（閾値を考える材料）の上位一覧
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

FEATS = ["ws_max", "ws_mean", "ws2_max", "hours_ws_ge6", "hours_ws_ge8", "rain_sum",
         "rain_max_1h", "hours_rain_ge1", "rain_while_windy", "rain_72h", "ws_max_72h", "rh_mean"]


def main():
    ds = pd.read_csv("data/dataset.csv", parse_dates=["date"])
    pos, neg = ds[ds.label == 1], ds[ds.label == 0]
    print(f"倒伏あり {len(pos)} 日 / 報告なし {len(neg)} 日\n")

    print("== 1. 日単位の検定（倒伏ありの日 vs 報告なしの日）")
    print(f"{'特徴量':18} {'あり中央値':>10} {'なし中央値':>10} {'効果量r':>8} {'p値':>9}")
    res = []
    for f in FEATS:
        u = stats.mannwhitneyu(pos[f], neg[f], alternative="two-sided")
        r = 2 * u.statistic / (len(pos) * len(neg)) - 1  # 順位二系列相関
        res.append((f, pos[f].median(), neg[f].median(), r, u.pvalue))
    for f, a, b, r, pv in sorted(res, key=lambda x: -abs(x[3])):
        print(f"{f:18} {a:10.1f} {b:10.1f} {r:+8.2f} {pv:9.1e}")
    print(f"（{len(FEATS)} 個を検定したので、Bonferroni 補正後の有意水準は {0.05 / len(FEATS):.4f}）\n")

    print("== 2. イベント単位: 期間内の最大値が、報告なしの日の何パーセンタイルか")
    key = ["ws_max_72h", "rain_72h", "rain_while_windy", "hours_ws_ge6"]
    print(f"{'期間':23} {'地域':14} {'確度':6} " + " ".join(f"{k:>16}" for k in key))
    for (cause, region), g in pos.groupby(["cause", "region"], sort=False):
        cells = []
        for k in key:
            v = g[k].max()
            cells.append(f"{v:6.1f}({stats.percentileofscore(neg[k], v):4.0f}%)")
        span = f"{g.date.min():%Y-%m-%d}〜{g.date.max():%m-%d}"
        print(f"{span:23} {region:14} {g.confidence.iloc[0]:6} " + " ".join(f"{c:>16}" for c in cells))

    print("\n== 3. 風雨が強かったのに倒伏の報告がない日（上位 15）")
    z = neg.copy()
    for k in key:
        z[f"r_{k}"] = z[k].rank(pct=True)
    z["score"] = z[[f"r_{k}" for k in key]].mean(axis=1)
    cols = ["date", "region"] + key
    print(z.sort_values("score", ascending=False)[cols].head(15).to_string(index=False,
          formatters={"date": lambda d: f"{d:%Y-%m-%d}"}))


if __name__ == "__main__":
    main()
