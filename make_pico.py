# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy"]
# ///
"""統一モデルの係数（results/unified_model.json）を埋め込んだ、Raspberry Pi Pico 用の MicroPython プログラム pico/main.py を作る。

Pico では numpy もファイルも使わず、math だけで判断する。係数を学習し直したら、これを実行し直す。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

from demo_lodging import SCENARIOS  # noqa: E402
from lodging_unified import FORECAST_FACTOR, VARIETY_RAIN_FACTOR  # noqa: E402

TEMPLATE = '''# Raspberry Pi Pico（MicroPython）で動く、台風のときの「刈る／待ってよい」判断（統一モデル）
# このファイルは make_pico.py が自動で作る。手で直さない。係数: results/unified_model.json
# 使い方: Thonny で Pico に main.py として保存し、実行する（docs/pico.md）
import gc
import math
import time

P = {params}
FORECAST_FACTOR = {ff}
VARIETY_RAIN_FACTOR = {vrf}
SCENARIOS = {scen}

try:
    from machine import Pin
    try:
        LED = Pin("LED", Pin.OUT)
    except Exception:
        LED = Pin(25, Pin.OUT)  # 古いファームウェアの Pico
except ImportError:
    LED = None  # PC で試すとき


def decide(pref, rain_past_mm, rain_forecast_mm, wind_ms, gdd=None, variety="koshihikari"):
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


def main():
    gc.collect()
    print("倒伏（台風）の刈り取り判断 - 統一モデル on Raspberry Pi Pico")
    if hasattr(gc, "mem_free"):
        print("空きメモリ", gc.mem_free(), "バイト（Pico の RAM は 264 KB）")
    for title, kw in SCENARIOS:
        t0 = time.ticks_us() if hasattr(time, "ticks_us") else 0
        harvest, p, thr = decide(**kw)
        us = time.ticks_diff(time.ticks_us(), t0) if hasattr(time, "ticks_us") else 0
        print("■", title, "(" + kw["pref"] + ")")
        print("  判断:", "【刈る】" if harvest else "【待ってよい】",
              "確率 {{:.0f}}%（閾値 {{:.0f}}%、計算 {{}} マイクロ秒）".format(p * 100, thr * 100, us))
        if LED is not None:
            LED.value(1 if harvest else 0)  # 刈る＝点灯、待ってよい＝消灯
            time.sleep(2)
    if LED is not None:
        LED.value(0)
    print("※ 架空の入力によるデモ。最終判断は農家と地元の専門家が行う")


main()
'''


def main():
    P = json.loads(Path("results/unified_model.json").read_text())
    keep = {k: P[k] for k in ("intercept", "rain", "wind", "pref", "threshold_national")}
    keep["local"] = {k: {kk: v[kk] for kk in ("prefs", "d", "e_ripe", "gdd_window", "threshold")}
                     for k, v in P["local"].items()}
    scen = [(t, {k: v for k, v in kw.items() if v is not None}) for t, kw in SCENARIOS]
    src = TEMPLATE.format(params=repr(keep), ff=repr(FORECAST_FACTOR), vrf=repr(VARIETY_RAIN_FACTOR),
                          scen=repr(scen))
    out = Path("pico/main.py")
    out.write_text(src, encoding="utf-8")
    print(f"保存: {out}（{len(src.encode())} バイト）")


if __name__ == "__main__":
    main()
