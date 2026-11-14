"""統一モデルで「刈る／待ってよい」を出す（実行時の部分。numpy だけで動く、4 コア CPU で 1 ミリ秒未満）。

係数は unified_model.py が results/unified_model.json に保存したもの:
  logit P = 全国の部分［雨＋風＋都道府県の補正］ ＋ 地域の追加項［d ＋ e·実り具合の時期］（茨城・千葉だけ）
- 雨: 最接近の前 2 日〜後 1 日の 4 日雨量（GPM IMERG。これからの分は GEOS-FP の予報）
- 風: NASA の 10 m 最大風速（学習は POWER、予報は GEOS-FP。どちらも同じ GEOS 系のモデル）
- 実り具合: 品種別の出穂後積算気温（NASA POWER の気温から phenology.py で推定）

仮置き（根拠のデータなし。地元で確かめるべき点）:
- 品種の係数: 背の低い品種は倒れにくい（ヒアリング）。雨をこの係数で割ってから入れる
- 予報の余裕: 予報の雨は 1.5 倍して入れる（GEOS-FP の過去の予報が約 2 週間しか残らず、誤差を評価できないので安全側）
限界: 茨城・千葉の検証（台風 23 個、1 つ抜き）では、2019 年 15 号（房総半島台風）を見逃した。
小さく強い台風では、NASA の風（約 50 km の格子）が弱く出る。
"""
import json
from pathlib import Path

import numpy as np

PARAMS = Path(__file__).resolve().parent / "results/unified_model.json"
FORECAST_FACTOR = 1.5
VARIETY_RAIN_FACTOR = {"koshihikari": 1.0, "akitakomachi": 1.2, "fukumaru": 1.5, "nijinokirameki": 2.0}
VARIETY_JA = {"koshihikari": "コシヒカリ", "akitakomachi": "あきたこまち",
              "fukumaru": "ふくまる", "nijinokirameki": "にじのきらめき"}


def load(path=PARAMS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def local_for(pref, P):
    for name, loc in P["local"].items():
        if pref in loc["prefs"]:
            return name, loc
    return None, None


def decide(pref, rain_past_mm, rain_forecast_mm, wind_ms, gdd=None, variety="koshihikari", P=None):
    """判断・確率・理由を返す。gdd は地域の追加項がある県（茨城・千葉）でだけ使う。"""
    P = P or load()
    if pref not in P["pref"]:
        raise ValueError(f"学習にない都道府県です: {pref}")
    vf = VARIETY_RAIN_FACTOR[variety]
    rain = (rain_past_mm + FORECAST_FACTOR * rain_forecast_mm) / vf
    z = (P["intercept"]
         + P["rain"]["coef"] * (np.log1p(rain) - P["rain"]["mu"]) / P["rain"]["sd"]
         + P["wind"]["coef"] * (wind_ms - P["wind"]["mu"]) / P["wind"]["sd"]
         + P["pref"][pref])
    name, loc = local_for(pref, P)
    use_local = loc is not None and gdd is not None
    # 地域の追加項は、その地域の県の補正の平均の上で学習したので、同じものを使う
    pc = np.mean([P["pref"][q] for q in loc["prefs"]]) if use_local else P["pref"][pref]
    z += pc - P["pref"][pref]
    reasons = [f"雨 {rain_past_mm:.0f} mm（過去）＋ {rain_forecast_mm:.0f} mm（予報、安全側に 1.5 倍）"
               + (f"、{VARIETY_JA[variety]}は倒れにくいので {vf:g} で割る" if vf != 1 else ""),
               f"風 {wind_ms:.1f} m/s（NASA の 10 m 最大風速）",
               (f"{name}の補正 {pc:+.2f}" if use_local else f"{pref}の補正 {pc:+.2f}")
               + "（同じ雨風でも被害の出やすさが地域で違う）"]
    if use_local:
        lo, hi = loc["gdd_window"]
        ripe = lo <= gdd < hi
        z += loc["d"] + loc["e_ripe"] * ripe
        thr = loc["threshold"]
        if gdd < lo:
            reasons.append(f"稲がまだ実りきっていない（出穂後 {gdd:.0f}℃ < {lo:.0f}℃）ので倒れにくい［{name}の地域の知見］")
        elif gdd >= hi:
            reasons.append(f"出穂後 {gdd:.0f}℃ で、収穫の時期を過ぎている［{name}の地域の知見］")
        else:
            reasons.append(f"稲が実って倒れやすい時期（出穂後 {gdd:.0f}℃）［{name}の地域の知見］")
    else:
        thr = P["threshold_national"]
        reasons.append("実り具合はこの県では使わない（品種・作付け時期の前提がないため、全国の部分だけで判断）")
    p = float(1 / (1 + np.exp(-z)))
    harvest = p >= thr
    return {"harvest": harvest, "decision": "刈る" if harvest else "待ってよい",
            "probability": p, "threshold": thr, "reasons": reasons}
