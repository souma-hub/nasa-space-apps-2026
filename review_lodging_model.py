# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""茨城・千葉の倒伏予測モデルのレビュー（頑健性と有意性の確認）。結果は results/model_review.txt。"""
import sys, itertools
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
from scipy import stats
from analyze_disasters import best_track
from analyze_early_harvest import fit_rule
tb = pd.read_csv("results/early_harvest_typhoons.csv")
tb["コシ出穂後"] = tb["コシ出穂後"].astype(float)

def loo(t):
    pred = []
    for i in range(len(t)):
        R, G, _ = fit_rule(t.drop(t.index[i]))
        r = t.iloc[i]; g = r["コシ出穂後"] if r["コシ出穂後"] == r["コシ出穂後"] else 9999
        pred.append(bool(r["雨IMERG"] >= R and g >= G))
    pred = np.array(pred); y = t["被害あり"].values
    return int((y & ~pred).sum()), int(y.sum()), int((~y & ~pred).sum()), int((~y).sum()), pred

print("== 1. 被害ありの基準を変える")
for ha in (50, 100, 200, 500, 1000):
    t = tb.copy(); t["被害あり"] = t["被害ha"] >= ha
    R, G, h = fit_rule(t); m, n, s, k, _ = loo(t)
    print(f"  {ha:5} ha 以上: 被害あり {n} 個 → 規則 R={R} G={G}、刈る {int(h.sum())}/22 | 1つ抜き 見逃し {m}/{n}、待ってよい {s}/{k}")

print("== 2. 2016 年 7 号と 9 号の重複")
for name, mask in (("7 号を被害なしにする", tb["台風"].str.contains("2016 第7号")),
                   ("9 号を被害なしにする", tb["台風"].str.contains("2016 第9号")),
                   ("7 号を除く", None)):
    t = tb.copy()
    if mask is None:
        t = t[~t["台風"].str.contains("2016 第7号")].reset_index(drop=True)
    else:
        t.loc[mask, "被害あり"] = False
    R, G, h = fit_rule(t); m, n, s, k, _ = loo(t)
    print(f"  {name}: 規則 R={R} G={G} | 1つ抜き 見逃し {m}/{n}、待ってよい {s}/{k}")

print("== 3. 雨の集計期間を変える（IMERG の日付は世界時）")
ds = pd.read_csv("data/dataset.csv", parse_dates=["date"]).set_index("date")
bst = best_track()
for a, b in ((-2, 1), (-3, 1), (-2, 2), (-1, 1), (-3, 0)):
    t = tb.copy(); rain = []
    for r in t.itertuples():
        d = pd.Timestamp(r.最接近)
        rain.append(ds.imerg_mean.loc[d + pd.Timedelta(days=a): d + pd.Timedelta(days=b)].sum())
    t["雨IMERG"] = rain
    R, G, h = fit_rule(t); m, n, s, k, _ = loo(t)
    print(f"  {a:+d}〜{b:+d} 日: 規則 R={R} G={G} | 1つ抜き 見逃し {m}/{n}、待ってよい {s}/{k}")

print("== 4. 偶然でないか（1つ抜きの予測と被害の関係、Fisher の正確確率検定 と 並べ替え検定）")
m, n, s, k, pred = loo(tb); y = tb["被害あり"].values
tab = [[int((y & pred).sum()), int((y & ~pred).sum())], [int((~y & pred).sum()), int((~y & ~pred).sum())]]
print(f"  表 [被害あり: 刈る, 待つ] [被害なし: 刈る, 待つ] = {tab}, Fisher 片側 p={stats.fisher_exact(tab, alternative='greater').pvalue:.3f}")
rng = np.random.default_rng(0); obs = s - m * 3; cnt = 0; N = 200
for _ in range(N):
    t = tb.copy(); t["被害あり"] = rng.permutation(t["被害あり"].values)
    mm, _, ss, _, _ = loo(t)
    cnt += (ss - mm * 3) >= obs
print(f"  並べ替え検定（得点 = 待ってよい − 3×見逃し、{N} 回）: p={cnt / N:.3f}")

print("== 5. 学習に使っていない 2022〜2026 年の台風（関東南部 300 km 以内、8〜9 月）")
t2 = bst[(bst.km <= 300) & bst.jst.dt.month.isin([8, 9]) & (bst.year >= 2022)]
for r in t2.itertuples():
    d = r.jst.normalize()
    rain = ds.imerg_mean.loc[d - pd.Timedelta(days=2): d + pd.Timedelta(days=1)].sum()
    g = ds.gdd_koshihikari.get(d, np.nan)
    print(f"  {r.year} 第{r.num}号 {d.date()} {r.km:.0f}km: 雨 {rain:.0f} mm、コシ出穂後 {g:.0f}℃ → {'刈る' if rain >= 30 and 400 <= g < 1500 else '待ってよい'}")
