# Raspberry Pi Pico 単体デモ: 台風のときの「刈る／待ってよい」判断（統一モデル）
# このファイルは make_pico.py が自動で作る。手で直さない。係数: results/unified_model.json
# 使い方: Pico に main.py として保存して USB 給電するだけ（docs/pico.md の「発表当日の手順」）
import gc
import json
import math
import select
import sys
import time

P = {'intercept': -3.0299595969814077, 'rain': {'mu': 3.3930042270164344, 'sd': 1.3409508329730118, 'coef': 1.5903052568289386}, 'wind': {'mu': 9.603250688705234, 'sd': 4.507960875762698, 'coef': 1.2496106597805783}, 'pref': {'三重': 0.9550331387566682, '京都': -0.16353398171373842, '佐賀': 0.5791532740524579, '兵庫': 0.2620499663396886, '北海道': 1.6478836740024025, '千葉': -0.3985673081556815, '和歌山': -0.44275229449708126, '埼玉': 0.03536094175220354, '大分': 0.5530637940023084, '大阪': -0.5025884708777585, '奈良': -0.8291732538803201, '宮城': 0.9896226645821244, '宮崎': 1.0549498547106186, '富山': -0.35888423399164515, '山口': -0.29704486781683476, '山形': -0.4562234416674226, '山梨': 0.03313306098608921, '岐阜': -0.21404428977966625, '岡山': 0.08660505285567309, '岩手': 1.8670973342303616, '島根': -1.3397649816556172, '広島': 0.03860719207543101, '徳島': 0.9604861262148996, '愛媛': 0.16378053057875877, '愛知': 0.449130060127679, '新潟': 0.21724820504657702, '東京': -1.9133427980696611, '栃木': 0.6151210350130443, '沖縄': -2.863283007801907, '滋賀': -0.6244158183335099, '熊本': 0.7094899914493609, '石川': -1.4896690303922004, '神奈川': -0.8152468766257265, '福井': -0.6229505555728208, '福岡': 0.6919054814677559, '福島': -0.2578359863899585, '秋田': 0.06467649923671859, '群馬': 0.24163738167483936, '茨城': 0.7531326931715284, '長崎': 0.38205992819653145, '長野': -0.7554195922272393, '青森': 0.6428133058499554, '静岡': 0.7939697547910639, '香川': -0.05347053808083162, '高知': -0.6014152720436471, '鳥取': -0.3471072331738802, '鹿児島': -0.02455617557319613}, 'threshold_national': 0.08936650682654564, 'local': {'茨城・千葉': {'prefs': ['茨城', '千葉'], 'd': -0.13792100786503125, 'e_ripe': 0.6515994520698931, 'gdd_window': [400.0, 1500.0], 'threshold': 0.16740144030960005}}}
FORECAST_FACTOR = 1.5
VARIETY_RAIN_FACTOR = {'koshihikari': 1.0, 'akitakomachi': 1.2, 'fukumaru': 1.5, 'nijinokirameki': 2.0}
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



def led(on):
    if LED is not None:
        LED.value(1 if on else 0)


def judge(kw, src):
    # decide を呼んで、LED を結果にし、JSON 1 行を print する。ボタンもシリアルもここを通る（判断は同じ decide）
    t0 = time.ticks_us()
    harvest, p, thr = decide(**kw)
    us = time.ticks_diff(time.ticks_us(), t0)
    led(harvest)  # 刈る＝点灯したまま、待ってよい＝消灯
    print(json.dumps({"src": src, "harvest": harvest, "decision": "刈る" if harvest else "待ってよい",
                      "prob": round(p, 4), "threshold": round(thr, 4), "us": us, "pref": kw["pref"]}))
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
        print(json.dumps({"error": str(e)}))
        return
    judge(kw, "serial")


def main():
    gc.collect()
    led(1)  # 起動の合図: 1 秒点灯 → 消灯
    time.sleep(1)
    led(0)
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    state = {"i": 0}
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
            if ch == "\n":
                on_line(buf)
                buf = ""
            elif ch != "\r":
                buf += ch
        time.sleep_ms(20)


main()
