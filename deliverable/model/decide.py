"""Standalone typhoon "harvest now / safe to wait" decision (unified model).

Pure Python standard library. Same logic as the Raspberry Pi Pico program.
Coefficients are read from unified_model.json, which sits next to this file.

CLI:
    python decide.py <pref> <rain_past_mm> <rain_forecast_mm> <wind_ms> [gdd] [variety]
Prints JSON: {"decision": "harvest now" | "safe to wait", "prob": ..., "threshold": ...}

<pref> is a prefecture name in Japanese (e.g. 茨城) or romanized (e.g. ibaraki).
[variety] is one of koshihikari (default), akitakomachi, fukumaru, nijinokirameki.
Decision support only: prefecture level, not a field-level forecast.
"""
import json
import math
import sys
from pathlib import Path

P = json.loads((Path(__file__).resolve().parent / "unified_model.json").read_text(encoding="utf-8"))

FORECAST_FACTOR = 1.5
VARIETY_RAIN_FACTOR = {"koshihikari": 1.0, "akitakomachi": 1.2, "fukumaru": 1.5, "nijinokirameki": 2.0}

_ROMAN = {
    "hokkaido": "北海道", "aomori": "青森", "iwate": "岩手", "miyagi": "宮城", "akita": "秋田",
    "yamagata": "山形", "fukushima": "福島", "ibaraki": "茨城", "tochigi": "栃木", "gunma": "群馬",
    "saitama": "埼玉", "chiba": "千葉", "tokyo": "東京", "kanagawa": "神奈川", "niigata": "新潟",
    "toyama": "富山", "ishikawa": "石川", "fukui": "福井", "yamanashi": "山梨", "nagano": "長野",
    "gifu": "岐阜", "shizuoka": "静岡", "aichi": "愛知", "mie": "三重", "shiga": "滋賀",
    "kyoto": "京都", "osaka": "大阪", "hyogo": "兵庫", "nara": "奈良", "wakayama": "和歌山",
    "tottori": "鳥取", "shimane": "島根", "okayama": "岡山", "hiroshima": "広島", "yamaguchi": "山口",
    "tokushima": "徳島", "kagawa": "香川", "ehime": "愛媛", "kochi": "高知", "fukuoka": "福岡",
    "saga": "佐賀", "nagasaki": "長崎", "kumamoto": "熊本", "oita": "大分", "miyazaki": "宮崎",
    "kagoshima": "鹿児島", "okinawa": "沖縄",
}


def normalize_pref(pref):
    p = pref.strip()
    p = _ROMAN.get(p.lower(), p)
    if p not in P["pref"] and p[:-1] in P["pref"] and p[-1] in "県府都":
        p = p[:-1]
    if p not in P["pref"]:
        raise ValueError("unknown prefecture: " + pref)
    return p


def decide(pref, rain_past_mm, rain_forecast_mm, wind_ms, gdd=None, variety="koshihikari"):
    """Return (harvest, prob, threshold)."""
    pref = normalize_pref(pref)
    rain = (rain_past_mm + FORECAST_FACTOR * rain_forecast_mm) / VARIETY_RAIN_FACTOR[variety]
    z = (P["intercept"]
         + P["rain"]["coef"] * (math.log(1 + rain) - P["rain"]["mu"]) / P["rain"]["sd"]
         + P["wind"]["coef"] * (wind_ms - P["wind"]["mu"]) / P["wind"]["sd"])
    loc = None
    for v in P["local"].values():
        if pref in v["prefs"]:
            loc = v
    if loc is not None and gdd is not None:
        z += sum(P["pref"][q] for q in loc["prefs"]) / len(loc["prefs"])
        z += loc["d"] + loc["e_ripe"] * (1 if loc["gdd_window"][0] <= gdd < loc["gdd_window"][1] else 0)
        thr = loc["threshold"]
    else:
        z += P["pref"][pref]
        thr = P["threshold_national"]
    p = 1 / (1 + math.exp(-z))
    return p >= thr, p, thr


def main(argv):
    if len(argv) < 5 or len(argv) > 7:
        print(__doc__)
        return 2
    gdd = float(argv[5]) if len(argv) > 5 and argv[5] != "" else None
    variety = argv[6] if len(argv) > 6 else "koshihikari"
    if variety not in VARIETY_RAIN_FACTOR:
        print("unknown variety: " + variety, file=sys.stderr)
        return 2
    try:
        harvest, p, thr = decide(argv[1], float(argv[2]), float(argv[3]), float(argv[4]), gdd, variety)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(json.dumps({"decision": "harvest now" if harvest else "safe to wait",
                      "prob": round(p, 4), "threshold": round(thr, 4)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
