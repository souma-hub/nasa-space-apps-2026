"""品種ごとの生育段階（出穂日と出穂後の積算気温）を、NASA POWER の日平均気温から推定する。

ヒアリング（2026-11-14）:
- 稲が青いうちはあまり倒れない（実って穂が重くなってから倒れやすい）
- 背が低い品種は倒れにくい
- 茨城南部〜千葉北部の主な品種: コシヒカリ、ふくまる、あきたこまち、にじのきらめき
- 台風の予報が出ると、早めに刈り取る（刈った田は倒れない）

推定の仕組み（簡易。値はすべて仮で、要確認）:
1. 5/1 からの有効積算温度（日平均気温 − 10℃ の合計）が、品種ごとの閾値に達した日を出穂日とする。
   閾値は、全年の平均出穂日が下の HEADING の典型日になるように、年をまたいで合わせ込む
2. 出穂後の積算気温（日平均気温の合計）で実り具合を表す。600℃ ごろから穂が黄色く重くなり、
   1,000℃ ごろが収穫の目安（一般的な目安）。ただし実際の倒伏は 457〜1,310℃ で起きていたので、
   400〜1,500℃ を「倒れうる時期」とする（1,500℃ を超えたら刈り取り済みとみなす）
3. 「倒れやすい田の割合」= Σ 作付割合 × 倒れやすさ × [400 ≤ 出穂後積算 < 1500]
   精度を上げるには、農水省の作況調査にある県別の出穂期の実績で合わせ込む
"""
import numpy as np
import pandas as pd

# 品種: (典型的な出穂日 MM-DD, 作付割合の仮置き, 倒れやすさ 0〜1 の仮置き)
VARIETIES = {
    "akitakomachi": ("07-20", 0.15, 0.8),
    "koshihikari": ("07-28", 0.60, 1.0),
    "fukumaru": ("08-03", 0.10, 0.5),
    "nijinokirameki": ("08-08", 0.15, 0.4),
}
BASE_T = 10.0
# 実際の倒伏（2026-08 は コシヒカリ出穂後 457℃、2019-09 は 1,142℃、2023-09 は 1,310℃）に合わせて広げた。
# 収穫の目安（約 1,000℃）を過ぎても、刈り取りまでの間は田に残って倒れうる
RIPE_FROM, HARVESTED_AT = 400.0, 1500.0


def heading_dates(t2m):
    """日平均気温（日付 index、5〜9 月）→ {品種: {年: 出穂日}}。"""
    eff = (t2m - BASE_T).clip(lower=0)
    cum = eff.groupby(eff.index.year).cumsum()
    out = {}
    for v, (mmdd, _, _) in VARIETIES.items():
        # 典型日の積算値を年ごとに測り、その平均を閾値にする
        typ = [cum[f"{y}-{mmdd}"] for y in sorted(set(cum.index.year)) if f"{y}-{mmdd}" in cum.index]
        thr = float(np.mean(typ))
        out[v] = {y: g[g >= thr].index.min() for y, g in cum.groupby(cum.index.year)}
    return out


def stage_features(t2m):
    """日ごとに、品種別の出穂後積算気温と、倒れやすい田の割合（加重）を返す。"""
    hd = heading_dates(t2m)
    f = pd.DataFrame(index=t2m.index)
    risk = pd.Series(0.0, index=t2m.index)
    for v, (_, share, weak) in VARIETIES.items():
        after = pd.Series(np.nan, index=t2m.index)
        for y, d in hd[v].items():
            m = (t2m.index.year == y) & (t2m.index >= d)
            after[m] = t2m[m].cumsum()
        f[f"gdd_{v}"] = after
        ripe = ((after >= RIPE_FROM) & (after < HARVESTED_AT)).astype(float)
        risk += share * weak * ripe
    f["exposed_weighted"] = risk
    f["heading_koshihikari_doy"] = [hd["koshihikari"][y].dayofyear for y in t2m.index.year]
    return f
