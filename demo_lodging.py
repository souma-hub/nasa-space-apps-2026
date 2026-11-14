# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "httpx", "python-dotenv"]
# ///
"""統一モデルのデモ。架空の台風の入力で「刈る／待ってよい」を出す（ネットワーク不要、numpy だけ）。

使い方:
  uv run demo_lodging.py                       # 用意した架空のシナリオをまとめて判断する
  uv run demo_lodging.py --pref 茨城 --past 40 --forecast 80 --wind 18 --gdd 900
  uv run demo_lodging.py --pref 鹿児島 --past 30 --forecast 120 --wind 22
入力の意味は lodging_unified.py を参照。実データでの判断は predict_lodging.py。
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

from lodging_unified import VARIETY_JA, decide, load  # noqa: E402

# 架空のシナリオ（数字はすべて作り物。判断の違いが分かるように選んだ）
SCENARIOS = [
    ("強い台風が直撃、稲は実っている", dict(pref="茨城", rain_past_mm=40, rain_forecast_mm=80, wind_ms=18, gdd=900)),
    ("同じ台風、ただし稲がまだ実りきっていない（強い台風なので、それでも刈る）",
     dict(pref="茨城", rain_past_mm=40, rain_forecast_mm=80, wind_ms=18, gdd=250)),
    ("台風が遠くを通る（雨も風も弱い）", dict(pref="千葉", rain_past_mm=5, rain_forecast_mm=15, wind_ms=9, gdd=900)),
    ("雨は多いが風は弱い", dict(pref="千葉", rain_past_mm=30, rain_forecast_mm=40, wind_ms=8, gdd=900)),
    ("中くらいの台風、倒れにくい品種", dict(pref="茨城", rain_past_mm=15, rain_forecast_mm=25, wind_ms=12, gdd=900,
                                     variety="nijinokirameki")),
    ("中くらいの台風、コシヒカリ", dict(pref="茨城", rain_past_mm=15, rain_forecast_mm=25, wind_ms=12, gdd=900)),
    ("中くらいの台風、ただし稲がまだ実りきっていない", dict(pref="茨城", rain_past_mm=15, rain_forecast_mm=25, wind_ms=12, gdd=250)),
    ("全国の部分だけ: 九州に強い台風", dict(pref="鹿児島", rain_past_mm=60, rain_forecast_mm=100, wind_ms=20)),
    ("全国の部分だけ: 東北をかすめる台風", dict(pref="宮城", rain_past_mm=10, rain_forecast_mm=20, wind_ms=11)),
    ("全国の部分だけ: 北陸、雨だけ少し", dict(pref="新潟", rain_past_mm=10, rain_forecast_mm=15, wind_ms=8)),
]


def show(title, kw, P):
    t0 = time.perf_counter()
    r = decide(P=P, **kw)
    ms = (time.perf_counter() - t0) * 1000
    v = VARIETY_JA[kw.get("variety", "koshihikari")]
    print(f"■ {title}（{kw['pref']}、{v}）")
    print(f"  判断: 【{r['decision']}】 被害が出る確率の目安 {r['probability']:.0%}（閾値 {r['threshold']:.0%}、計算 {ms:.2f} ms）")
    for s in r["reasons"]:
        print(f"   - {s}")


def main():
    a = argparse.ArgumentParser(description="統一モデルのデモ（架空の入力）")
    a.add_argument("--pref", help="都道府県（例: 茨城、鹿児島）")
    a.add_argument("--past", type=float, default=0, help="過去 2 日の雨 mm")
    a.add_argument("--forecast", type=float, default=0, help="これから 2 日の予報の雨 mm")
    a.add_argument("--wind", type=float, default=10, help="10 m 最大風速 m/s")
    a.add_argument("--gdd", type=float, help="出穂後積算気温（茨城・千葉だけ使う）")
    a.add_argument("--variety", default="koshihikari", choices=list(VARIETY_JA))
    x = a.parse_args()
    P = load()
    if x.pref:
        show("入力した条件", dict(pref=x.pref, rain_past_mm=x.past, rain_forecast_mm=x.forecast,
                                 wind_ms=x.wind, gdd=x.gdd, variety=x.variety), P)
    else:
        for title, kw in SCENARIOS:
            show(title, kw, P)
            print()
    print("※ 支援の道具であり、最終判断は農家と地元の専門家が行う。数字は架空の入力によるデモ")


if __name__ == "__main__":
    main()
