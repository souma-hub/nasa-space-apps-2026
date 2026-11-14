# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""全国モデルで「風（NASA POWER）」が本質的に効いているのか、台風との距離の代わりなのかを調べる。

- 風を抜いた「雨だけ」（茨城・千葉モデルとそろえる）と、雨＋風を比べる（台風を 1 つずつ抜く交差検証）
- 風と距離の相関、雨＋距離、雨＋距離＋風（距離を入れた上で風がまだ効くか）を見る
差の 95% 区間は台風単位のブートストラップ（analyze_japan_location.py と同じ）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from analyze_japan_location import REGION, boot_diff, cv, scores  # noqa: E402

MODELS = {
    "雨だけ（茨城・千葉とそろえる）": (["lrain"], None),
    "雨＋風": (["lrain", "ws10m_max_3d"], None),
    "雨＋距離": (["lrain", "lkm"], None),
    "雨＋距離＋風": (["lrain", "lkm", "ws10m_max_3d"], None),
    "雨＋都道府県": (["lrain"], "pref"),
    "雨＋風＋都道府県": (["lrain", "ws10m_max_3d"], "pref"),
}


def main():
    d = pd.read_csv("data/japan_typhoon_dataset.csv")
    d = d[~d.shared_table].reset_index(drop=True)
    d["tid"] = d.year.astype(str) + "-" + d.typhoon_num.astype(str)
    d["region"] = d.pref.map(REGION)
    d["lrain"] = np.log1p(d.rain_4d_imerg)
    d["lkm"] = np.log1p(d.closest_km)
    y = d.damaged.astype(int).values

    r = stats.spearmanr(d.ws10m_max_3d, d.closest_km)
    print(f"風と台風との距離の相関（Spearman）: ρ={r.statistic:+.2f}（p={r.pvalue:.1e}）")
    r = stats.spearmanr(d.rain_4d_imerg, d.closest_km)
    print(f"雨と台風との距離の相関（Spearman）: ρ={r.statistic:+.2f}（p={r.pvalue:.1e}）\n")

    print("== 台風を 1 つずつ抜く交差検証（［ ］は比べる相手との差の 95% 区間、台風単位）")
    preds = {}
    for name, (cols, cat) in MODELS.items():
        preds[name] = cv(d, y, cols, cat, "lr", d.tid.values)
        s = scores(y, preds[name])
        print(f"  {name:22} AUC {s['auc']:.3f}  待ってよい {s['wait']:.0%}  Brier {s['brier']:.4f}")
    for base, new in (("雨だけ（茨城・千葉とそろえる）", "雨＋風"), ("雨だけ（茨城・千葉とそろえる）", "雨＋距離"),
                      ("雨＋距離", "雨＋距離＋風"), ("雨＋風", "雨＋距離＋風"),
                      ("雨＋都道府県", "雨＋風＋都道府県")):
        (a_lo, w_lo, b_lo), (a_hi, w_hi, b_hi) = boot_diff(d, y, preds[base], preds[new])
        print(f"  {new} − {base}: AUC［{a_lo:+.3f}, {a_hi:+.3f}］ 待ってよい［{w_lo:+.0%}, {w_hi:+.0%}］"
              f" Brier［{b_lo:+.4f}, {b_hi:+.4f}］")


if __name__ == "__main__":
    main()
