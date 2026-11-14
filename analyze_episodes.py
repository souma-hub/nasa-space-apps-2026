# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy"]
# ///
"""嵐（風雨の強い日のまとまり）ごとに、倒伏イベントの位置を調べる。

嵐の定義: アメダスの地域最大瞬間風速 15 m/s 以上、または地域平均の日雨量 30 mm 以上の日。
1 日以内の間隔でつながる日を 1 つの嵐とみなし、嵐の中の最大値・合計で特徴を作る。
events.csv の期間と重なる嵐を「倒伏あり」、それ以外を「報告なし」とする（倒伏なしとは限らない）。
被害はあったが倒伏かどうか分からない嵐（label が NaN）は、倒伏の比較から外す。冠水も同じ規則で別に比べる。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

GUST, RAIN = 15.0, 30.0


def tri(s):
    """嵐の中の日ごとのラベル → 1（どこかで 1）/ NaN（不明を含む）/ 0。"""
    return 1.0 if (s == 1).any() else np.nan if s.isna().any() else 0.0


def main():
    d = pd.read_csv("data/dataset.csv", parse_dates=["date"]).sort_values("date")
    storm = (d.am_gust_max >= GUST) | (d.am_rain_mean >= RAIN)
    s = d[storm].copy()
    gap = s.date.diff().dt.days.fillna(99)
    s["ep"] = (gap > 2).cumsum()
    ep = s.groupby("ep").agg(
        start=("date", "min"), end=("date", "max"), days=("date", "size"),
        gust=("am_gust_max", "max"), wsmax=("am_wsmax_max", "max"),
        rain=("am_rain_mean", "sum"), rain_1h=("am_rain_1h_max", "max"),
        label=("label", tri), flood=("flood", tri))
    ep.to_csv("data/episodes.csv", index=False)
    pos, neg = ep[ep.label == 1], ep[ep.label == 0]
    print(f"嵐 {len(ep)} 個（2001〜2026 年の 8〜9 月）: 倒伏あり {len(pos)} / 倒伏不明 "
          f"{int(ep.label.isna().sum())} / 報告なし {len(neg)}\n")
    print("== 倒伏ありの嵐の順位（全 {} 個中、大きい順）".format(len(ep)))
    for f in ("gust", "wsmax", "rain", "rain_1h"):
        ep[f"rk_{f}"] = ep[f].rank(ascending=False, method="min")
    print(ep[(ep.label == 1) | (ep.flood == 1) | ep.label.isna()][
        ["start", "end", "label", "flood", "gust", "rk_gust", "wsmax", "rk_wsmax", "rain",
         "rk_rain"]].to_string(index=False, float_format="%.1f"))
    for name, col in (("倒伏", "label"), ("冠水", "flood")):
        a, b = ep[ep[col] == 1], ep[ep[col] == 0]
        print(f"\n== 検定（{name}ありの嵐 {len(a)} 個 vs 報告なし {len(b)} 個、片側 Mann-Whitney）")
        for f in ("gust", "wsmax", "rain", "rain_1h"):
            u = stats.mannwhitneyu(a[f].dropna(), b[f].dropna(), alternative="greater")
            print(f"  {f:8}: あり中央値 {a[f].median():6.1f} / 報告なし {b[f].median():6.1f}, p={u.pvalue:.3f}")
    # 嵐の規模（風と雨の順位の平均）で上から並べたとき、倒伏ありがどこに来るか
    ep["score"] = (ep.gust.rank(pct=True) + ep.rain.rank(pct=True)) / 2
    top = ep.sort_values("score", ascending=False).reset_index(drop=True)
    print("\n== 風と雨の順位の平均で上位 12 の嵐（label: 倒伏 1=あり NaN=不明 0=報告なし、flood: 冠水）")
    print(top.head(12)[["start", "end", "gust", "wsmax", "rain", "label", "flood"]].to_string(
        float_format="%.1f"))


if __name__ == "__main__":
    main()
