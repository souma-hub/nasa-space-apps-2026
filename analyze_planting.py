# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""品種と田植え日を変えると、稲が台風に弱い時期が台風の来る時期からどれだけ外れるかを、過去の台風で数える。

Field Shift（作付けの選択肢を 3 通り以上比べる）への答え。
- 気温: NASA POWER の日別 T2M（35.90N, 140.20E, 1981〜2025）
- 出穂日: phenology.py と同じ考え方（5/1 からの有効積算温度が品種ごとの閾値に達した日）。田植えを s 日ずらすと起点が 5/1+s 日になる
- 弱い時期: 出穂後の積算気温が 400〜1,500℃。うち 400〜900℃ は適期前（刈れば早刈りになる時期）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analyze_disasters import best_track  # noqa: E402
from lodging_unified import decide  # noqa: E402
from phenology import BASE_T, HARVESTED_AT, RIPE_FROM, VARIETIES  # noqa: E402

OPTIMAL_FROM = 900.0  # これ未満で刈ると早刈り
NEAR_KM = 300
Y0, Y1 = 1981, 2025
STRATEGIES = [  # (ラベル, 品種キー, ずらし日数)
    ("今のやり方（コシヒカリ）", "koshihikari", 0),
    ("田植えを3週間遅らせる（コシヒカリ）", "koshihikari", 21),
    ("早生品種にする（あきたこまち）", "akitakomachi", 0),
    ("晩生品種にする（にじのきらめき）", "nijinokirameki", 0),
]
SHIFTS = [-14, 0, 14, 28]


def load_t2m(cache=Path("data/power_t2m_planting.csv")):
    if not cache.exists():
        r = httpx.get("https://power.larc.nasa.gov/api/temporal/daily/point", timeout=180, params=dict(
            parameters="T2M", community="AG", latitude=35.90, longitude=140.20,
            start=f"{Y0}0101", end=f"{Y1}1231", format="JSON"))
        r.raise_for_status()
        d = r.json()["properties"]["parameter"]["T2M"]
        pd.DataFrame({"date": list(d), "T2M": list(d.values())}).to_csv(cache, index=False, encoding="utf-8")
    df = pd.read_csv(cache, encoding="utf-8", dtype={"date": str})
    s = pd.Series(df["T2M"].values, index=pd.to_datetime(df["date"], format="%Y%m%d"))
    return s.where(s > -900).interpolate(method="linear", limit_direction="both")  # 欠測(-999)は線形補間


def thresholds(t2m):
    """品種ごとの出穂の閾値: 各年の 5/1 から典型出穂日までの有効積算温度の全年平均。"""
    eff = (t2m - BASE_T).clip(lower=0)
    out = {}
    for v, (mmdd, _, _) in VARIETIES.items():
        out[v] = float(np.mean([eff[f"{y}-05-01":f"{y}-{mmdd}"].sum() for y in range(Y0, Y1 + 1)]))
    return out


def gdd_table(t2m, thr, v, shift):
    """年ごとの (出穂日, 5/1〜11/30 の日別 出穂後積算気温) を返す。出穂前は NaN。"""
    eff = (t2m - BASE_T).clip(lower=0)
    heads, gdd = {}, []
    for y in range(Y0, Y1 + 1):
        start = pd.Timestamp(f"{y}-05-01") + pd.Timedelta(days=shift)
        cum = eff[start:f"{y}-11-30"].cumsum()
        h = cum.index[cum >= thr[v]].min()
        heads[y] = h
        days = t2m[f"{y}-05-01":f"{y}-11-30"]
        g = pd.Series(np.nan, index=days.index)
        if pd.notna(h):
            g[days.index >= h] = days[days.index >= h].cumsum()
        gdd.append(g)
    return heads, pd.concat(gdd)


def md(doy_mean):
    """2001 年（平年）の通日の平均 → MM-DD。"""
    return (pd.Timestamp("2001-01-01") + pd.Timedelta(days=round(doy_mean) - 1)).strftime("%m-%d")


def doy(d):
    return d.replace(year=2001).day_of_year


def weak_period(gdd):
    """年ごとの弱い時期の (開始日, 終了日) の平均 MM-DD。終了は 1,500℃ に達した日（未達なら 11/30）。"""
    s, e = [], []
    for y, g in gdd.groupby(gdd.index.year):
        a, b = g.index[g >= RIPE_FROM], g.index[g >= HARVESTED_AT]
        if len(a):
            s.append(doy(a.min()))
            e.append(doy(b.min() if len(b) else g.index.max()))
    return md(np.mean(s)), md(np.mean(e))


def overlap(gdd, dates):
    """台風の最接近日ごとの gdd（出穂前・範囲外は NaN）、弱い時期か、適期前か。"""
    g = np.array([gdd.get(d, np.nan) for d in dates])
    weak = (g >= RIPE_FROM) & (g < HARVESTED_AT)
    return g, weak, weak & (g < OPTIMAL_FROM)


def main():
    Path("data").mkdir(exist_ok=True)
    t2m = load_t2m()
    thr = thresholds(t2m)
    bst = best_track()
    ty = bst[bst.year.between(Y0, Y1) & bst.jst.dt.month.isin([7, 8, 9, 10]) & (bst.km <= NEAR_KM)]
    dates = list(ty.jst.dt.normalize())
    ty_year = ty.year.values
    nty = len(dates)
    tb = pd.read_csv("results/unified_kanto_loo.csv", encoding="utf-8", parse_dates=["最接近"])
    P = json.loads(Path("results/unified_model.json").read_text(encoding="utf-8"))
    nyear = Y1 - Y0 + 1

    lines = [f"== 台風に弱い時期を、品種と田植え日でずらす（35.90N, 140.20E, NASA POWER T2M {Y0}〜{Y1}）",
             "出穂の閾値（5/1 からの有効積算温度, ℃）: " + "、".join(f"{v} {x:.0f}" for v, x in thr.items()),
             f"対象の台風: {Y0}〜{Y1} 年の 7〜10 月に最接近、{NEAR_KM} km 以内 = {nty} 個\n"]
    rows, a_rows = [], []
    for label, v, s in STRATEGIES:
        heads, gdd = gdd_table(t2m, thr, v, s)
        ws, we = weak_period(gdd)
        g, weak, pre = overlap(gdd, dates)
        # B: 検証済み 23 台風
        gb = np.array([gdd.get(d, np.nan) for d in tb["最接近"]])
        dec = [decide("茨城", rain_past_mm=r.雨IMERG, rain_forecast_mm=0, wind_ms=r.風POWER,
                      gdd=0 if np.isnan(x) else x, variety="koshihikari", P=P)["harvest"]
               for r, x in zip(tb.itertuples(), gb)]
        dec = np.array(dec)
        done = gb >= HARVESTED_AT
        cut = dec & ~done
        bweak = (gb >= RIPE_FROM) & (gb < HARVESTED_AT)
        dmg = tb["被害あり"].values.astype(bool)
        row = {
            "戦略": label, "品種": v, "ずらし日": s,
            "平均出穂日": md(np.mean([doy(h) for h in heads.values()])),
            "弱い時期の開始": ws, "弱い時期の終了": we,
            "A_台風数": nty, "A_弱い時期に重なった台風": int(weak.sum()), "A_うち適期前": int(pre.sum()),
            "A_重なった年数": len(set(ty_year[weak])), "A_年数": nyear,
            "B_台風数": len(tb), "B_刈る": int(cut.sum()), "B_うち900未満(早刈り)": int((cut & (gb < OPTIMAL_FROM)).sum()),
            "B_収穫済み(1500以上)": int(done.sum()), "B_被害ありで弱い時期に重なった": int((dmg & bweak).sum()),
            "B_被害あり数": int(dmg.sum()),
        }
        rows.append(row)
        if s == 0 and v == "koshihikari":
            gb0 = gb
    res = pd.DataFrame(rows)

    lines.append("== A. 長期（7〜10 月の全台風）")
    a = res[["戦略", "平均出穂日", "弱い時期の開始", "弱い時期の終了"]].copy()
    a["重なった台風"] = [f"{r.A_弱い時期に重なった台風}/{r.A_台風数}" for r in res.itertuples()]
    a["うち適期前"] = res["A_うち適期前"]
    a["重なった年"] = [f"{r.A_重なった年数}/{r.A_年数}" for r in res.itertuples()]
    lines.append(a.to_string(index=False))

    lines.append("\n付録: 4 品種 × 田植えのずらし（日）で、弱い時期に重なった台風の数（／適期前に重なった数）")
    app = {}
    for v in VARIETIES:
        app[v] = {}
        for s in SHIFTS:
            _, gdd = gdd_table(t2m, thr, v, s)
            _, w, p = overlap(gdd, dates)
            app[v][f"{s:+d}日"] = f"{int(w.sum())} ({int(p.sum())})"
    lines.append(pd.DataFrame(app).T.to_string())

    lines.append(f"\n== B. 検証済みの {len(tb)} 台風（{tb['最接近'].dt.year.min()}〜{tb['最接近'].dt.year.max()} 年 8〜9 月）で見た判断")
    lines.append("判断は decide(茨城, 雨IMERG, 予報 0, 風POWER, gdd) で、品種の雨の係数は根拠のない仮置きなので全戦略で koshihikari に固定。"
                 "gdd が出穂前なら 0、1,500℃ 以上は『収穫済み』として別に数える")
    b = res[["戦略"]].copy()
    b["刈る"] = res["B_刈る"]
    b["うち900℃未満(早刈り)"] = res["B_うち900未満(早刈り)"]
    b["収穫済み"] = res["B_収穫済み(1500以上)"]
    b["被害ありで弱い時期に重なった"] = [f"{r.B_被害ありで弱い時期に重なった}/{r.B_被害あり数}" for r in res.itertuples()]
    lines.append(b.to_string(index=False))
    diff = np.abs(gb0 - tb["コシ出穂後"].values)
    lines.append(f"\n健全性チェック（戦略 1 の gdd と CSV「コシ出穂後」の差）: 最大 {np.nanmax(diff):.0f}℃、平均 {np.nanmean(diff):.0f}℃"
                 "（閾値を合わせた年の範囲が違うので完全一致はしない）")
    lines.append("""
注意:
①出穂日は気温だけの簡易推定で、日長への反応（コシヒカリは田植えを遅らせても出穂はそれほど遅れない）を入れていない。田植えを遅らせる戦略は、実際より出穂が遅れる前提になっている
②B は 8〜9 月の台風だけなので、弱い時期が 10 月にずれる戦略を有利に見せる。長期の A（7〜10 月）と合わせて読む
③数えたのは弱い時期に台風が重なった回数であって、被害の回数ではない
④収量・品質・作業の都合は比べていない
⑤1 地点（35.9N, 140.2E）の気温だけで見ている""")
    report = "\n".join(lines)
    print(report)
    Path("results/planting_report.txt").write_text(report + "\n", encoding="utf-8")
    res.to_csv("results/planting_strategies.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
