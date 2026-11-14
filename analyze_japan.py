# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""全国の「都道府県 × 台風」（data/japan_typhoon_dataset.csv）で、茨城・千葉と同じ手順の解析とモデル構築をする。

- 対象: 2004〜2021 年、最接近が 8〜9 月、代表座標から 500 km 以内。被害あり = 水稲被害 100 ha 以上
- 複数の台風が 1 つの表にまとまった行（shared_table）は、どの台風の被害か分からないので外す
- 解析: 被害あり／なしで、雨（IMERG）・風（POWER WS10M_MAX）・距離・生育の進み具合（5/1 からの有効積算温度）を比べる
- モデル: 台風を 1 つずつ丸ごと抜く交差検証（同じ台風の他県から答えが漏れないように）で AUC を比べる
- 茨城・千葉の規則（雨 30 mm 以上）を全国にそのまま当てた場合も見る
入力はすべて NASA のデータ（IMERG、POWER）。都道府県の緯度は代表座標（県庁所在地）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402


def main():
    d = pd.read_csv("data/japan_typhoon_dataset.csv")
    d = d[~d.shared_table].copy()
    d["tid"] = d.year.astype(str) + "-" + d.typhoon_num.astype(str)
    d["lrain"] = np.log1p(d.rain_4d_imerg)
    d["heat"] = d.eff_heat_may1 / 1000
    d["heat2"] = d.heat ** 2
    y = d.damaged.astype(int).values
    print(f"行 {len(d)}（台風 {d.tid.nunique()} 個、都道府県 {d.pref.nunique()}）、被害あり {y.sum()} 行\n")

    print("== 解析（被害あり vs なし、片側 Mann-Whitney。距離は小さい方が被害ありの向き）")
    for c, alt, lab in (("rain_4d_imerg", "greater", "4 日雨量 IMERG"), ("ws10m_max_3d", "greater", "最大風速 POWER"),
                        ("closest_km", "less", "最接近距離"), ("eff_heat_may1", "greater", "5/1 からの有効積算温度")):
        a, b = d[c][y == 1], d[c][y == 0]
        u = stats.mannwhitneyu(a, b, alternative=alt)
        print(f"  {lab:16}: あり中央値 {a.median():7.1f} / なし {b.median():7.1f}, p={u.pvalue:.1e}")

    models = {
        "雨だけ": ["lrain"],
        "雨＋生育（2 次）": ["lrain", "heat", "heat2"],
        "雨＋生育＋緯度": ["lrain", "heat", "heat2", "lat"],
        "雨＋生育＋緯度＋風": ["lrain", "heat", "heat2", "lat", "ws10m_max_3d"],
        "雨＋生育＋緯度＋風＋距離": ["lrain", "heat", "heat2", "lat", "ws10m_max_3d", "closest_km"],
    }
    print("\n== モデル（台風を 1 つずつ抜く交差検証の AUC と、被害ありの 95% を拾う閾値で『待ってよい』と言えた被害なしの割合）")
    tids = d.tid.unique()
    res = {}
    for name, cols in list(models.items()) + [("勾配ブースティング（全部）", models["雨＋生育＋緯度＋風＋距離"])]:
        pred = np.zeros(len(d))
        x = d[cols].values
        for t in tids:
            te = (d.tid == t).values
            if name.startswith("勾配"):
                m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                                   l2_regularization=1.0, random_state=0)
            else:
                m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))
            m.fit(x[~te], y[~te])
            pred[te] = m.predict_proba(x[te])[:, 1]
        auc = roc_auc_score(y, pred)
        thr = np.quantile(pred[y == 1], 0.05)
        wait = np.mean(pred[y == 0] < thr)
        # 台風単位のブートストラップで AUC の 95% 区間
        rng = np.random.default_rng(0)
        boots = []
        for _ in range(300):
            pick = rng.choice(tids, len(tids))
            idx = np.concatenate([np.where(d.tid.values == t)[0] for t in pick])
            if y[idx].min() != y[idx].max():
                boots.append(roc_auc_score(y[idx], pred[idx]))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        res[name] = pred
        print(f"  {name:22}: AUC {auc:.3f}（95% 区間 {lo:.2f}〜{hi:.2f}）、待ってよい {wait:.0%}")

    print("\n== 茨城・千葉の規則（雨 30 mm 以上なら刈る）を全国にそのまま当てた場合")
    h = d.rain_4d_imerg >= 30
    print(f"  被害ありの拾い {np.mean(h[y == 1]):.0%}、被害なしで『待ってよい』 {np.mean(~h[y == 0]):.0%}")
    for name in ("茨城", "千葉"):
        s = d[d.pref == name]
        print(f"  {name}: 行 {len(s)}、被害あり {int(s.damaged.sum())}")
    d.assign(**{f"pred_{k}": v for k, v in res.items()}).to_csv("results/japan_predictions.csv", index=False)


if __name__ == "__main__":
    main()
