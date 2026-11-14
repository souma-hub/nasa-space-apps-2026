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

DECIDE_SRC = '''def decide(pref, rain_past_mm, rain_forecast_mm, wind_ms, gdd=None, variety="koshihikari"):
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
'''

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


{decide}

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

# 単体デモ版。Pico に main.py として保存すると、USB 給電だけで起動する（発表当日用）
#  - ボタン（BOOTSEL）を押すたびに 2 つのシナリオを交互に判断し、LED で出す
#  - 同時に USB シリアルで 1 行 "県,過去雨,予報雨,風,gdd[,品種]" を受け取り、JSON 1 行で答える
DEMO_TEMPLATE = '''# Raspberry Pi Pico 単体デモ: 台風のときの「刈る／待ってよい」判断（統一モデル）
# このファイルは make_pico.py が自動で作る。手で直さない。係数: results/unified_model.json
# 使い方: Pico に main.py として保存して USB 給電するだけ（docs/pico.md の「発表当日の手順」）
import gc
import json
import math
import select
import sys
import time

P = {params}
FORECAST_FACTOR = {ff}
VARIETY_RAIN_FACTOR = {vrf}
# ボタンで交互に出すシナリオ（demo_lodging.py と同じ値）
DEMO = [
    ("強い台風が直撃、稲は実っている", dict(pref="茨城", rain_past_mm=40, rain_forecast_mm=80, wind_ms=18, gdd=900)),
    ("台風が遠くを通る", dict(pref="千葉", rain_past_mm=5, rain_forecast_mm=15, wind_ms=9, gdd=900)),
]

try:
    from machine import Pin
    try:
        LED = Pin("LED", Pin.OUT)
    except Exception:
        LED = Pin(25, Pin.OUT)  # 古いファームウェアの Pico
except ImportError:
    LED = None  # PC で試すとき

try:
    from rp2 import bootsel_button
except ImportError:
    def bootsel_button():
        return 0


{decide}


def led(on):
    if LED is not None:
        LED.value(1 if on else 0)


def judge(kw, src):
    # decide を呼んで、LED を結果にし、JSON 1 行を print する。ボタンもシリアルもここを通る（判断は同じ decide）
    t0 = time.ticks_us()
    harvest, p, thr = decide(**kw)
    us = time.ticks_diff(time.ticks_us(), t0)
    led(harvest)  # 刈る＝点灯したまま、待ってよい＝消灯
    print(json.dumps({{"src": src, "harvest": harvest, "decision": "刈る" if harvest else "待ってよい",
                      "prob": round(p, 4), "threshold": round(thr, 4), "us": us, "pref": kw["pref"]}}))
    return harvest


def blink3():
    # 「計算した」合図: 短く 3 回点滅
    for _ in range(3):
        led(1)
        time.sleep_ms(120)
        led(0)
        time.sleep_ms(120)


def on_button(state):
    # ボタンが押されたとき: 3 回点滅 → 次のシナリオを判断（交互）
    title, kw = DEMO[state["i"] % len(DEMO)]
    state["i"] += 1
    blink3()
    judge(kw, "button")


def parse_line(line):
    f = [x.strip() for x in line.split(",")]
    if len(f) < 5 or len(f) > 6:
        raise ValueError("pref,past,forecast,wind,gdd[,variety] の形で送る")
    pref = f[0]
    if pref not in P["pref"]:
        raise ValueError("学習にない都道府県: " + pref)
    variety = f[5] if len(f) == 6 and f[5] else "koshihikari"
    if variety not in VARIETY_RAIN_FACTOR:
        raise ValueError("未知の品種: " + variety)
    return dict(pref=pref, rain_past_mm=float(f[1]), rain_forecast_mm=float(f[2]), wind_ms=float(f[3]),
                gdd=float(f[4]) if f[4] != "" else None, variety=variety)


def on_line(line):
    line = line.strip()
    if not line:
        return
    try:
        kw = parse_line(line)
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))
        return
    judge(kw, "serial")


def main():
    gc.collect()
    led(1)  # 起動の合図: 1 秒点灯 → 消灯
    time.sleep(1)
    led(0)
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    state = {{"i": 0}}
    buf = ""
    was_down = False
    while True:
        down = bool(bootsel_button())
        if down and not was_down:
            on_button(state)
        was_down = down
        while poll.poll(0):  # 非ブロッキングで 1 文字ずつ読む
            ch = sys.stdin.read(1)
            if not ch:
                break
            if ch == "\\n":
                on_line(buf)
                buf = ""
            elif ch != "\\r":
                buf += ch
        time.sleep_ms(20)


main()
'''


def main():
    P = json.loads(Path("results/unified_model.json").read_text(encoding="utf-8"))
    keep = {k: P[k] for k in ("intercept", "rain", "wind", "pref", "threshold_national")}
    keep["local"] = {k: {kk: v[kk] for kk in ("prefs", "d", "e_ripe", "gdd_window", "threshold")}
                     for k, v in P["local"].items()}
    scen = [(t, {k: v for k, v in kw.items() if v is not None}) for t, kw in SCENARIOS]
    common = dict(params=repr(keep), ff=repr(FORECAST_FACTOR), vrf=repr(VARIETY_RAIN_FACTOR),
                  decide=DECIDE_SRC)
    for out, src in (
        (Path("pico/main.py"), TEMPLATE.format(scen=repr(scen), **common)),
        (Path("pico/demo_main.py"), DEMO_TEMPLATE.format(**common)),
    ):
        out.write_text(src, encoding="utf-8")
        print(f"保存: {out}（{len(src.encode())} バイト）")


if __name__ == "__main__":
    main()
