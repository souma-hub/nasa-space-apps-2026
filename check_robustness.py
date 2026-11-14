"""レビュー V1（感度分析）と V3（並べ替え検定・陰性対照）を、手元の 23 台風だけで行う。
入力: results/unified_kanto_loo.csv, results/unified_model.json（decide は lodging_unified.py）
出力: results/robustness_report.txt  再学習はしない（全国の学習データは不要）。
"""
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lodging_unified import decide, load  # noqa: E402

SEED = 20261115
N_PERM, N_NEG = 10000, 1000
RAIN_M = [0.5, 0.75, 1.25, 1.5, 2.0]
WIND_M = [0.7, 0.85, 1.15, 1.3]
RAIN_ALL = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
WIND_ALL = [0.7, 0.85, 1.0, 1.15, 1.3]

P = load()
with open(ROOT / "results/unified_kanto_loo.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
name = [r["台風"] for r in rows]
rain = np.array([float(r["雨IMERG"]) for r in rows])
wind = np.array([float(r["風POWER"]) for r in rows])
gdd = np.array([float(r["コシ出穂後"]) for r in rows])
dmg = np.array([r["被害あり"] == "True" for r in rows])
p_loo = np.array([float(r["p_unified"]) for r in rows])
h_loo = np.array([r["harvest_unified"] == "True" for r in rows])
n, npos = len(rows), int(dmg.sum())
nneg = n - npos


def dec(rn, wd):
    """茨城・予報 0・コシヒカリで decide を呼ぶ。"""
    return np.array([decide("茨城", rain_past_mm=a, rain_forecast_mm=0, wind_ms=b, gdd=g,
                            variety="koshihikari", P=P)["harvest"] for a, b, g in zip(rn, wd, gdd)])


def auc(p, lab):
    pos, neg = p[lab], p[~lab]
    return ((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg))


base = dec(rain, wind)
L = []
w = L.append

# ---------- V1 ----------
grid = {(rm, wm): dec(rain * rm, wind * wm) for rm in RAIN_ALL for wm in WIND_ALL}


def cell(rm, wm):
    d = grid[(rm, wm)]
    return int((base & ~d).sum()), int((~base & d).sum())  # 危険側, 安全側


# ---------- V3 ----------
rng = np.random.default_rng(SEED)
thr_act = p_loo[dmg].min()
wait_act = int((~dmg & (p_loo < thr_act)).sum())
auc_act = auc(p_loo, dmg)
cnt_ge = auc_ge = both_ge = 0
waits, aucs = [], []
for _ in range(N_PERM):
    lab = rng.permutation(dmg)
    t = p_loo[lab].min()
    wc = int((~lab & (p_loo < t)).sum())
    a = auc(p_loo, lab)
    waits.append(wc)
    aucs.append(a)
    cnt_ge += wc >= wait_act
    auc_ge += a >= auc_act - 1e-12
    both_ge += (wc >= wait_act) and (a >= auc_act - 1e-12)
waits, aucs = np.array(waits), np.array(aucs)
p_wait, p_auc, p_both = (cnt_ge + 1) / (N_PERM + 1), (auc_ge + 1) / (N_PERM + 1), (both_ge + 1) / (N_PERM + 1)


def metrics(d):
    return (int((d == dmg).sum()), int((dmg & ~d).sum()), int((~dmg & ~d).sum()), int(d.sum()))


act = metrics(base)
neg_m = np.array([metrics(dec(rain[i], wind[i])) for i in (rng.permutation(n) for _ in range(N_NEG))], dtype=float)
neg2 = np.array([metrics(dec(rain[rng.permutation(n)], wind[rng.permutation(n)])) for _ in range(N_NEG)], dtype=float)

# ---------- 出力 ----------
loo_mis = int((dmg & ~h_loo).sum())
loo_wait = int((~dmg & ~h_loo).sum())
mild = [(rm, wm) for rm in (0.75, 1.0, 1.25) for wm in (0.85, 1.0, 1.15)]
mild_worst = max(int((base & ~grid[k] & dmg).sum()) for k in mild)
base_hit = int((base & dmg).sum())
w("【結論（発表の質疑で言える形）】")
w(f"1. 雨を 0.75〜1.25 倍・風を 0.85〜1.15 倍に振っても、元の判断で刈るだった被害あり {base_hit} 個のうち"
  f"待ってよいに崩れるのは最大 {mild_worst} 個（全データ学習の in-sample の判断。1 つ抜きとは別物）。")
w(f"2. 被害ありの確率の最小値を閾値にして見逃し 0 のとき、被害なしの {wait_act}/{nneg} 個が待ってよいになる。"
  f"ラベルを 10,000 回入れ替えた検定で同じ以上になる割合は p = {p_wait:.4f}（AUC 基準 p = {p_auc:.4f}）。")
w(f"3. 別の台風の気象を入れた陰性対照（1,000 回平均）では、被害との一致は {act[0]}/{n} から {neg_m[:, 0].mean():.1f}/{n} に落ち、"
  f"見逃しは {act[1]} 個から平均 {neg_m[:, 1].mean():.1f} 個に増える。")
w("")
w(f"対象: 茨城・千葉の台風 {n} 個（被害あり {npos}、なし {nneg}）。乱数の種 {SEED}。再学習はしていない。")
w("")
w("=" * 70)
w("V1 感度分析（予報が外れたら判断は変わるか）")
w("=" * 70)
w("注意: ここでの判断は全データで学習したモデル（in-sample）の decide() の結果で、1 つ抜きの判断（p_unified, harvest_unified）とは別物。")
w("decide(茨城, 過去の雨=雨IMERG×倍率, 予報 0, 風=風POWER×倍率, gdd=コシ出穂後, コシヒカリ)。倍率 1 が元の判断。")
w(f"元の判断（in-sample）: 刈る {int(base.sum())} 個。被害あり {npos} 個のうち刈る {base_hit}、"
  f"被害なし {nneg} 個のうち待ってよい {int((~base & ~dmg).sum())}。")
w(f"（参考）1 つ抜きの判断: 被害あり {npos} 個のうち見逃し {loo_mis}、被害なし {nneg} 個のうち待ってよい {loo_wait}。"
  f"in-sample と 1 つ抜きで判断が違う台風: {int((base != h_loo).sum())} 個。")
w("")
w("表の見方: 各セルは「判断が変わった台風の数 危険側/安全側」。危険側 = 刈る→待ってよい、安全側 = 待ってよい→刈る。")
w("")
w("[片方ずつ振る]")
w("  雨の倍率    : " + "".join(f"x{m:<8g}" for m in RAIN_M))
w("  危険/安全   : " + "".join(f"{'%d/%d' % cell(m, 1.0):<9}" for m in RAIN_M))
w("  風の倍率    : " + "".join(f"x{m:<8g}" for m in WIND_M))
w("  危険/安全   : " + "".join(f"{'%d/%d' % cell(1.0, m):<9}" for m in WIND_M))
w("")
w("[雨 × 風の格子]  セル = 危険側/安全側（合計）")
w("  雨＼風     " + "".join(f"x{m:<11g}" for m in WIND_ALL))
for rm in RAIN_ALL:
    cs = []
    for wm in WIND_ALL:
        a, b = cell(rm, wm)
        cs.append(f"{a}/{b} ({a + b})".ljust(12))
    w(f"  x{rm:<8g} " + "".join(cs))
w("")
w("[被害あり 7 個: 刈る→待ってよい（危険側に崩れる）が起きる倍率]")
for i in np.where(dmg)[0]:
    if not base[i]:
        state = "元から待ってよい（in-sample でも見逃し）"
    else:
        single = [f"雨x{m:g}" for m in RAIN_M if not grid[(m, 1.0)][i]] + [f"風x{m:g}" for m in WIND_M if not grid[(1.0, m)][i]]
        ge = sum(1 for rm in RAIN_M for wm in WIND_M if not grid[(rm, wm)][i])
        state = "片方ずつで崩れる倍率: " + (", ".join(single) if single else "なし") + f"／格子 20 組中 {ge} 組で崩れる"
    w(f"  {name[i]:<10} 雨{rain[i]:.0f}mm 風{wind[i]:.1f} gdd{gdd[i]:.0f} 判断={'刈る' if base[i] else '待ってよい'}  {state}")
w("")
w("[被害なしで待ってよいだった台風: 待ってよい→刈る（安全側に変わる）が起きる倍率]")
for i in np.where(~dmg & ~base)[0]:
    single = [f"雨x{m:g}" for m in RAIN_M if grid[(m, 1.0)][i]] + [f"風x{m:g}" for m in WIND_M if grid[(1.0, m)][i]]
    ge = sum(1 for rm in RAIN_M for wm in WIND_M if grid[(rm, wm)][i])
    w(f"  {name[i]:<10} 雨{rain[i]:.0f}mm 風{wind[i]:.1f} gdd{gdd[i]:.0f}  片方ずつで刈るに変わる倍率: "
      + (", ".join(single) if single else "なし") + f"／格子 20 組中 {ge} 組")
w("")
w("[被害なしで元から刈る（空振り）だった台風: 待ってよいに変わる倍率]")
for i in np.where(~dmg & base)[0]:
    single = [f"雨x{m:g}" for m in RAIN_M if not grid[(m, 1.0)][i]] + [f"風x{m:g}" for m in WIND_M if not grid[(1.0, m)][i]]
    w(f"  {name[i]:<10} 雨{rain[i]:.0f}mm 風{wind[i]:.1f} gdd{gdd[i]:.0f}  " + (", ".join(single) if single else "片方ずつでは変わらない"))
w("")
w("=" * 70)
w("V3 並べ替え検定（偶然でないか）")
w("=" * 70)
w(f"1 つ抜きの確率 p_unified を固定し、被害ありのラベル（{npos} 個）を {n} 台風の間で {N_PERM:,} 回ランダムに入れ替える。")
w("各回: 被害ありの確率の最小値を閾値（見逃し 0）にしたとき閾値未満になる被害なし（待ってよい）の数、と AUC（Mann-Whitney U / (7×16)、同点は 0.5）。")
w("p 値 = 入れ替え後の値が実際以上になる割合（実際の 1 回を含め (k+1)/(10000+1)）。")
w("")
w(f"  実際の AUC（手元メモ用。スライドには出さない）: {auc_act:.4f}")
w(f"  実際: 被害ありの確率の最小値 {thr_act:.4f}、閾値未満の被害なし（待ってよい）= {wait_act} / {nneg}")
w(f"  入れ替え後: 待ってよい数の平均 {waits.mean():.2f}（最大 {waits.max()}）、AUC の平均 {aucs.mean():.3f}（95 パーセンタイル {np.percentile(aucs, 95):.3f}）")
w(f"  p 値（待ってよい数が実際以上）: {p_wait:.4f}  （{cnt_ge} / {N_PERM}）")
w(f"  p 値（AUC が実際以上）        : {p_auc:.4f}  （{auc_ge} / {N_PERM}）")
w(f"  p 値（両方とも実際以上）      : {p_both:.4f}  （{both_ge} / {N_PERM}）")
w("")
w("陰性対照: 雨IMERG と風POWER を台風の間でシャッフル（別の台風の気象を入れる。gdd は元のまま）。decide（in-sample）の判断を 1,000 回平均。")
w(f"  {'指標':<28}{'実際':>6}{'(雨風の組をシャッフル)':>22}{'(雨と風を別々に)':>20}")
labels = ["被害の有無と判断の一致（/23）", "見逃し（被害あり→待ってよい）", "被害なしで待ってよい", "刈る台風の数"]
for k, lb in enumerate(labels):
    w(f"  {lb:<26}{act[k]:>8}{neg_m[:, k].mean():>18.2f}{neg2[:, k].mean():>20.2f}")
w(f"  一致が実際以上になった割合: 組 {np.mean(neg_m[:, 0] >= act[0]):.3f}、別々 {np.mean(neg2[:, 0] >= act[0]):.3f}")
w("")
w("限界: 23 台風・被害あり 7 個と小さい。1 つ抜きでも閾値や地域の知見は同じ地域の台風から決めた部分があり、p 値は偶然だけでは説明しにくいかの目安。")
(ROOT / "results/robustness_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
