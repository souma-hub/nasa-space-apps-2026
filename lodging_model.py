# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scikit-learn"]
# ///
"""台風・大雨のときに「刈る／待ってよい」を出す、軽量な倒伏予測モデル（茨城南部〜千葉北部）。

入力はすべて NASA のデータ:
- rain_mm: 嵐の前後 4 日の雨（過去 2 日は GPM IMERG、これから 2 日は GEOS-FP の予報）
- gdd: 選んだ品種の出穂後積算気温（NASA POWER の気温から phenology.py で推定）

モデル（results/early_harvest_typhoons.csv の 2004〜2021 年の台風 23 個で決めた）。現在は比較用で、採用は統一モデル（lodging_unified.py）:
1. 規則: rain_mm ≥ RAIN_MM × 品種の係数 × 予報の余裕 かつ gdd ≥ GDD なら「刈る」
   - 1 つ抜きの検証で、被害ありの見逃し 1/7、被害なし 16 個のうち 8 個で「待ってよい」
   - 風（POWER）は足すと悪化したので使わない（NASA の風は台風の突風を表せない）
2. ロジスティック回帰: 同じ 2 つの入力で「被害が出る確率」を表示用に出す

仮置き（根拠のデータなし。地元で確かめるべき点）:
- 品種の係数: 背の低い品種は倒れにくいので、雨の閾値を上げる
- 予報の余裕: GEOS-FP の過去の予報は約 2 週間分しか残っておらず、予報の誤差を評価できない。
  予報の雨が入るときは閾値を 2/3 にして安全側に倒す
動作要件: 4 コア CPU（学習も推論も 1 秒未満）。
"""
import json
import sys
from pathlib import Path

import numpy as np

RAIN_MM = 30.0   # IMERG の 4 日雨量の閾値（コシヒカリ基準）
GDD = 400.0      # 出穂後積算気温の閾値（これ未満は稲が青く、倒れにくい）
GDD_HARVESTED = 1500.0  # これを超えたら刈り取り済みとみなす（phenology.py と同じ）
FORECAST_MARGIN = 2 / 3
# 品種ごとの雨の閾値の係数（仮置き）。背の低い・倒れにくい品種ほど大きい
VARIETY_RAIN_FACTOR = {
    "koshihikari": 1.0, "akitakomachi": 1.2, "fukumaru": 1.5, "nijinokirameki": 2.0,
}
VARIETY_JA = {"koshihikari": "コシヒカリ", "akitakomachi": "あきたこまち",
              "fukumaru": "ふくまる", "nijinokirameki": "にじのきらめき"}
COEF_PATH = Path("results/lodging_logistic.json")


def fit_logistic(csv="results/early_harvest_typhoons.csv", out=COEF_PATH):
    """台風 23 個でロジスティック回帰を学習し、係数を JSON に保存する。"""
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    t = pd.read_csv(csv)
    g = t["コシ出穂後"].fillna(2000)
    # 危険度は「真ん中の時期だけ高い」山型（青いと倒れず、刈り取り後も倒れない）なので、時期に入っているかを使う
    x = np.c_[np.log1p(t["雨IMERG"]), ((g >= GDD) & (g < GDD_HARVESTED)).astype(float)]
    y = t["被害あり"].astype(int).values
    m = LogisticRegression(C=1.0).fit(x, y)
    coef = {"intercept": float(m.intercept_[0]), "log1p_rain": float(m.coef_[0][0]),
            "in_window": float(m.coef_[0][1]), "n": int(len(y)), "n_damage": int(y.sum())}
    out.write_text(json.dumps(coef, ensure_ascii=False, indent=2), encoding="utf-8")
    return coef


def probability(rain_mm, gdd, coef=None):
    c = coef or json.loads(COEF_PATH.read_text(encoding="utf-8"))
    z = (c["intercept"] + c["log1p_rain"] * np.log1p(rain_mm)
         + c["in_window"] * float(GDD <= gdd < GDD_HARVESTED))
    return float(1 / (1 + np.exp(-z)))


def decide(rain_past_mm, rain_forecast_mm, gdd, variety="koshihikari"):
    """判断と理由を返す。rain_forecast_mm が 0 より大きいときは予報の余裕を掛ける。"""
    rain = rain_past_mm + rain_forecast_mm
    thr = RAIN_MM * VARIETY_RAIN_FACTOR[variety]
    if rain_forecast_mm > 0:
        thr *= FORECAST_MARGIN
    ripe = GDD <= gdd < GDD_HARVESTED
    wet = rain >= thr
    harvest = bool(ripe and wet)
    reasons = []
    if gdd >= 1500:
        reasons.append(f"出穂後 {gdd:.0f}℃ で、すでに収穫の時期を過ぎている（刈り取り済みの可能性）")
    elif not ripe:
        reasons.append(f"稲がまだ実りきっていない（出穂後 {gdd:.0f}℃ < {GDD:.0f}℃）ので倒れにくく、刈ると損が大きい")
    else:
        reasons.append(f"稲が実っている（出穂後 {gdd:.0f}℃ ≥ {GDD:.0f}℃）")
    reasons.append(f"雨 {rain:.0f} mm（過去 {rain_past_mm:.0f} + 予報 {rain_forecast_mm:.0f}）"
                   f"{'≥' if wet else '<'} 閾値 {thr:.0f} mm（{VARIETY_JA[variety]}"
                   f"{'、予報の余裕込み' if rain_forecast_mm > 0 else ''}）")
    p = probability(rain, gdd) if COEF_PATH.exists() else float("nan")
    return {"harvest": harvest, "decision": "刈る" if harvest else "待ってよい",
            "probability": p, "rain_mm": rain, "threshold_mm": thr, "gdd": gdd,
            "reasons": reasons}


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import nasa_common  # noqa: F401  出力の UTF-8 固定のため
    c = fit_logistic()
    print("ロジスティック回帰の係数:", c)
    for args in ((60, 0, 800), (60, 0, 300), (20, 0, 900), (10, 40, 900), (60, 0, 800, "nijinokirameki")):
        print(args, decide(*args)["decision"], decide(*args)["reasons"])
