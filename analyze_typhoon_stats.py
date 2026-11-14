# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pandas", "numpy", "scipy"]
# ///
"""22 台風の表（results/early_harvest_typhoons.csv）で、被害あり／なしの差を検定する。発表の解析スライド用。

- 雨（NASA IMERG・POWER）、風（NASA POWER）、最大瞬間風速（気象庁アメダス、地上）、出穂後の積算気温を、
  被害あり（6）と被害なし（16）で比べる（片側 Mann-Whitney U、被害あり ＞ なし）
- 「雨だけ（IMERG 30 mm 以上）」と「雨かつ出穂後 400℃ 以上」を、片側 Fisher の正確検定で比べる
- 雨が 50 mm 以上の台風を、出穂後 400℃ の未満・以上で分けて、被害の数を数える

注意: 探索的な解析で、多重比較の補正はしていない。閾値（30 mm・400℃）は analyze_early_harvest.py が
過去に合わせて決めた値なので、Fisher の p 値は楽観的。被害は農水省の風水害の合計で、倒伏だけではない。
出力は results/typhoon_stats_report.txt。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

HERE = Path(__file__).resolve().parent
SRC = HERE / "results" / "early_harvest_typhoons.csv"
OUT = HERE / "results" / "typhoon_stats_report.txt"
RAIN_MM, GDD = 30, 400  # analyze_early_harvest.py の規則と同じ値


def main():
    d = pd.read_csv(SRC).rename(columns={
        "雨IMERG": "imerg", "雨POWER": "power", "風POWER": "wind_power",
        "コシ出穂後": "gdd", "瞬間風速(地上)": "gust", "被害あり": "dmg"})
    d["dmg"] = d["dmg"].astype(bool)
    lines = [f"台風 {len(d)} 個（被害あり {d.dmg.sum()} / なし {(~d.dmg).sum()}）", "",
             "== 被害あり／なしの比較（片側 Mann-Whitney U、被害あり ＞ なし）"]
    for col, label in (("imerg", "雨 NASA IMERG (mm)"), ("power", "雨 NASA POWER (mm)"),
                       ("wind_power", "風 NASA POWER 1時間平均の最大 (m/s)"),
                       ("gust", "最大瞬間風速 アメダス地上 (m/s)"), ("gdd", "出穂後の積算気温 コシヒカリ (℃)")):
        a, b = d.loc[d.dmg, col], d.loc[~d.dmg, col]
        p = stats.mannwhitneyu(a, b, alternative="greater").pvalue
        lines.append(f"  {label:34s} あり中央値 {a.median():7.1f} / なし中央値 {b.median():7.1f}  p={p:.3f}")

    both = (d.imerg >= RAIN_MM) & (d.gdd >= GDD)
    rain_only = d.imerg >= RAIN_MM
    lines += ["", f"== 規則の比較（片側 Fisher）。閾値は過去に合わせた値で、p 値は楽観的"]
    for name, flag in ((f"雨だけ（IMERG {RAIN_MM} mm 以上）", rain_only),
                       (f"雨かつ出穂後 {GDD}℃ 以上", both)):
        tab = pd.crosstab(flag, d.dmg).reindex(index=[False, True], columns=[False, True], fill_value=0)
        p = stats.fisher_exact(tab.values, alternative="greater")[1]
        lines.append(f"  {name}: 刈る {int(flag.sum())} 回（被害あり {int((flag & d.dmg).sum())}）  p={p:.3f}")

    big = d[d.imerg >= 50]
    lines += ["", f"== 雨 50 mm 以上の {len(big)} 回を、出穂後 {GDD}℃ で分ける（被害あり／回数）"]
    for name, sub in ((f"{GDD}℃ 未満（青い稲）", big[big.gdd < GDD]), (f"{GDD}℃ 以上", big[big.gdd >= GDD])):
        lines.append(f"  {name}: {int(sub.dmg.sum())} / {len(sub)}")
    lines.append("  青い稲（400℃ 未満）で雨 50 mm 以上の台風: " + "、".join(
        f"{r.台風}（雨 {r.imerg:.0f} mm, {r.gdd:.0f}℃）" for r in big[big.gdd < GDD].itertuples()))

    text = "\n".join(lines)
    print(text)
    OUT.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
