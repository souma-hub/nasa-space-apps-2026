# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""全国と茨城・千葉を 1 つの式にまとめた倒伏（水稲の風水害）予測モデルと、その検証。

式（ロジスティック回帰）:
  logit P = 全国の部分  [ a + b·log1p(雨) + c·風 + 都道府県の補正 ]        ← 全国のデータで学習
          + 地域の追加項 [ d + e·(実り具合の時期に入っているか) ]          ← 前提（品種・作付け時期）がある地域だけ
- 雨: GPM IMERG の 4 日雨量（最接近の前 2 日〜後 1 日）、風: NASA POWER の最大風速
- 地域の追加項は、全国の部分を固定（オフセット）して、その地域のデータだけで 2 つの係数を学習する
- 茨城・千葉の正解は「茨城＋千葉の水稲被害 100 ha 以上」なので、都道府県の補正は 2 県の平均を使い、ずれは d が吸収する

検証（茨城・千葉の台風 23 個、results/early_harvest_typhoons.csv）:
- 台風を 1 つずつ抜く。抜いた台風は全国の学習からも外す（他の県の答えから漏れないように）
- 閾値は学習側で「被害ありの見逃し 0」になる最大の確率にし、抜いた台風に当てる（今の規則と同じ決め方）
- 比べる相手: 今の規則（雨 30 mm かつ出穂後 400℃）、全国の部分だけ、全国＋地域の追加項
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from scipy.optimize import minimize  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

GDD, GDD_HARVESTED = 400.0, 1500.0
LOCAL_PREFS = ("茨城", "千葉")


class National:
    """全国の部分: 雨・風（標準化）＋都道府県のダミー。L2 正則化（C=1）。"""

    def fit(self, d, y):
        self.prefs = sorted(d.pref.unique())
        self.mu = d[["lrain", "ws10m_max_3d"]].mean().values
        self.sd = d[["lrain", "ws10m_max_3d"]].std().values
        self.m = LogisticRegression(C=1.0, max_iter=2000).fit(self._x(d.lrain, d.ws10m_max_3d, d.pref), y)
        return self

    def _x(self, lrain, wind, pref):
        num = (np.c_[lrain, wind] - self.mu) / self.sd
        dummy = np.array([[p == q for q in self.prefs] for p in pref], dtype=float)
        return np.c_[num, dummy]

    def logit(self, rain_mm, wind, prefs):
        """prefs を複数渡すと、その県の補正の平均を使う（茨城＋千葉の合算の正解に合わせる）。"""
        rain_mm, wind = np.atleast_1d(rain_mm), np.atleast_1d(wind)
        zs = [self.m.decision_function(self._x(np.log1p(rain_mm), wind, [p] * len(rain_mm))) for p in prefs]
        return np.mean(zs, axis=0)


def fit_local(offset, ripe, y, lam=1.0):
    """地域の追加項 d + e·ripe を、全国の部分を固定して学習する（係数に L2 をかけて分離を防ぐ）。"""
    def nll(w):
        z = offset + w[0] + w[1] * ripe
        return np.sum(np.logaddexp(0, z) - y * z) + lam * (w ** 2).sum() / 2
    return minimize(nll, np.zeros(2), method="BFGS").x


def load():
    nat = pd.read_csv("data/japan_typhoon_dataset.csv")
    nat = nat[~nat.shared_table].reset_index(drop=True)
    nat["tid"] = nat.year.astype(str) + "-" + nat.typhoon_num.astype(str)
    nat["lrain"] = np.log1p(nat.rain_4d_imerg)
    kt = pd.read_csv("results/early_harvest_typhoons.csv")
    kt["tid"] = kt["台風"].str.extract(r"(\d{4}) 第(\d+)号").agg("-".join, axis=1)
    g = kt["コシ出穂後"].fillna(9999)
    kt["ripe"] = ((g >= GDD) & (g < GDD_HARVESTED)).astype(float)
    return nat, kt


def loo(nat, kt):
    yk = kt["被害あり"].astype(int).values
    out = {k: np.zeros(len(kt)) for k in ("全国の部分だけ", "全国＋地域の追加項")}
    harvest = {k: np.zeros(len(kt), bool) for k in out}
    coefs = []
    for i, t in enumerate(kt.tid):
        n = nat[nat.tid != t]
        model = National().fit(n, n.damaged.astype(int).values)
        off = model.logit(kt["雨IMERG"], kt["風POWER"], LOCAL_PREFS)
        tr = np.arange(len(kt)) != i
        w = fit_local(off[tr], kt.ripe.values[tr], yk[tr])
        coefs.append(w)
        for k, z in (("全国の部分だけ", off), ("全国＋地域の追加項", off + w[0] + w[1] * kt.ripe.values)):
            p = 1 / (1 + np.exp(-z))
            thr = p[tr][yk[tr] == 1].min()  # 学習側で見逃し 0 になる最大の閾値
            out[k][i] = p[i]
            harvest[k][i] = p[i] >= thr
    return yk, out, harvest, np.array(coefs)


def main():
    nat, kt = load()
    yk, prob, harvest, coefs = loo(nat, kt)
    n1, n0 = yk.sum(), (1 - yk).sum()
    print(f"茨城・千葉の台風 {len(kt)} 個（被害あり {n1}）で、台風を 1 つずつ抜いて検証\n")
    rows = [("今の規則（雨 30 mm かつ出穂後 400℃）", kt["刈る_1つ抜き"].astype(bool).values, None)]
    rows += [(k, harvest[k], prob[k]) for k in prob]
    for name, h, p in rows:
        miss = int((~h & (yk == 1)).sum())
        wait = int((~h & (yk == 0)).sum())
        f = stats.fisher_exact([[int((h & (yk == 1)).sum()), miss], [n0 - wait, wait]], alternative="greater")
        auc = f"、AUC {roc_auc_score(yk, p):.2f}" if p is not None else ""
        print(f"  {name:34} 見逃し {miss}/{n1}、待ってよい {wait}/{n0}（Fisher 片側 p={f.pvalue:.3f}）{auc}")

    print("\n地域の追加項の係数（1 つ抜きの平均）: "
          f"d（地域のずれ）{coefs[:, 0].mean():+.2f}、e（実り具合の時期）{coefs[:, 1].mean():+.2f}")
    full = National().fit(nat, nat.damaged.astype(int).values)
    off = full.logit(kt["雨IMERG"], kt["風POWER"], LOCAL_PREFS)
    w = fit_local(off, kt.ripe.values, yk)
    print(f"全データで学習した地域の追加項: d {w[0]:+.2f}、e {w[1]:+.2f}")
    kt.assign(p_national=prob["全国の部分だけ"], p_unified=prob["全国＋地域の追加項"],
              harvest_unified=harvest["全国＋地域の追加項"]).to_csv("results/unified_kanto_loo.csv", index=False)


if __name__ == "__main__":
    main()
