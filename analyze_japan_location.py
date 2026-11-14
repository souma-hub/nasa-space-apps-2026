# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""全国モデルに「場所」の変数（緯度経度・地方・都道府県）を入れる価値があるかを切り分ける。

基準は「雨＋風」（analyze_japan.py で効いた 2 つ）。これに場所の変数を足したモデルを比べる。
- 良くなるか（見分ける力）: AUC、被害ありの 95% を拾う閾値で『待ってよい』と言えた割合
- 誤りが減るか（確率の当たり方）: Brier スコア、対数損失、地方ごとの「予測の合計 − 実際の数」
- 知らない土地でも使えるか: 地方を丸ごと抜いて当てる検証（都道府県・地方のダミーはここでは使えない）
差は台風単位のブートストラップ（対応あり）で 95% 区間を出す。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

REGION = {
    "北海道": "北海道",
    **dict.fromkeys(["青森", "岩手", "宮城", "秋田", "山形", "福島"], "東北"),
    **dict.fromkeys(["茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川"], "関東"),
    **dict.fromkeys(["新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知"], "中部"),
    **dict.fromkeys(["三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山"], "近畿"),
    **dict.fromkeys(["鳥取", "島根", "岡山", "広島", "山口"], "中国"),
    **dict.fromkeys(["徳島", "香川", "愛媛", "高知"], "四国"),
    **dict.fromkeys(["福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄"], "九州・沖縄"),
}
BASE = ["lrain", "ws10m_max_3d"]


def logit(cat=None, C=1.0):
    num = make_pipeline(StandardScaler())
    if cat is None:
        return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000))
    return lambda ncols: make_pipeline(
        ColumnTransformer([("n", num, ncols), ("c", OneHotEncoder(handle_unknown="ignore"), [cat])]),
        LogisticRegression(C=C, max_iter=2000))


MODELS = {
    # 名前: (数値の列, カテゴリの列, 作り方)
    "基準: 雨＋風": (BASE, None, "lr"),
    "＋緯度": (BASE + ["lat"], None, "lr"),
    "＋緯度＋経度": (BASE + ["lat", "lon"], None, "lr"),
    "＋緯度×雨（閾値が南北で変わる）": (BASE + ["lat", "lat_x_rain"], None, "lr"),
    "＋地方（8 区分）": (BASE, "region", "lr"),
    "＋都道府県（47、正則化）": (BASE, "pref", "lr"),
    "＋県の過去の被害率（学習側だけで計算）": (BASE + ["pref_rate"], None, "lr"),
    "勾配ブースティング 雨＋風": (BASE, None, "gb"),
    "勾配ブースティング 雨＋風＋緯度経度": (BASE + ["lat", "lon"], None, "gb"),
}


def make(cols, cat, kind):
    if kind == "gb":
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                              l2_regularization=1.0, random_state=0)
    if cat is None:
        return logit()
    return logit(cat)(cols)


def cv(d, y, cols, cat, kind, groups):
    pred = np.zeros(len(d))
    for g in np.unique(groups):
        te = groups == g
        tr = d[~te].copy()
        tst = d[te].copy()
        if "pref_rate" in cols:  # 県の被害率は学習側だけで計算（答えが漏れないように。少数は全国平均へ寄せる）
            prior, k = y[~te].mean(), 10
            s = pd.DataFrame({"pref": tr.pref, "y": y[~te]}).groupby("pref").y.agg(["sum", "count"])
            rate = (s["sum"] + k * prior) / (s["count"] + k)
            tr["pref_rate"] = tr.pref.map(rate).fillna(prior)
            tst["pref_rate"] = tst.pref.map(rate).fillna(prior)
        use = cols + ([cat] if cat else [])
        m = make(cols, cat, kind)
        m.fit(tr[use] if cat else tr[cols].values, y[~te])
        pred[te] = m.predict_proba(tst[use] if cat else tst[cols].values)[:, 1]
    return pred


def wait_rate(y, p):
    thr = np.quantile(p[y == 1], 0.05)
    return np.mean(p[y == 0] < thr)


def scores(y, p):
    return {"auc": roc_auc_score(y, p), "wait": wait_rate(y, p),
            "brier": brier_score_loss(y, p), "logloss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))}


def boot_diff(d, y, p0, p1, n=500):
    """台風単位のブートストラップで、基準との差（AUC・待ってよい・Brier）の 95% 区間。"""
    rng = np.random.default_rng(0)
    tids = d.tid.unique()
    idx_of = {t: np.where(d.tid.values == t)[0] for t in tids}
    out = []
    for _ in range(n):
        idx = np.concatenate([idx_of[t] for t in rng.choice(tids, len(tids))])
        if y[idx].min() == y[idx].max():
            continue
        a, b = scores(y[idx], p0[idx]), scores(y[idx], p1[idx])
        out.append((b["auc"] - a["auc"], b["wait"] - a["wait"], b["brier"] - a["brier"]))
    return np.percentile(np.array(out), [2.5, 97.5], axis=0)


def region_table(d, y, preds):
    rows = []
    for r, s in d.groupby("region"):
        i = s.index.values
        row = {"地方": r, "行": len(i), "被害あり": int(y[i].sum())}
        for name, p in preds.items():
            row[name] = p[i].sum() - y[i].sum()
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    d = pd.read_csv("data/japan_typhoon_dataset.csv")
    d = d[~d.shared_table].reset_index(drop=True)
    d["tid"] = d.year.astype(str) + "-" + d.typhoon_num.astype(str)
    d["region"] = d.pref.map(REGION)
    assert d.region.notna().all(), d.pref[d.region.isna()].unique()
    d["lrain"] = np.log1p(d.rain_4d_imerg)
    d["lat_x_rain"] = (d.lat - d.lat.mean()) * (d.lrain - d.lrain.mean())
    y = d.damaged.astype(int).values
    print(f"行 {len(d)}（台風 {d.tid.nunique()} 個）、被害あり {y.sum()} 行\n")

    print("== A. 台風を 1 つずつ抜く交差検証（場所の変数で、見分ける力と確率の当たり方が変わるか）")
    print("   AUC・待ってよいは高いほど良い。Brier・対数損失は低いほど良い。［ ］は基準との差の 95% 区間（台風単位）")
    preds = {}
    for name, (cols, cat, kind) in MODELS.items():
        p = cv(d, y, cols, cat, kind, d.tid.values)
        preds[name] = p
        s = scores(y, p)
        line = (f"  {name:28} AUC {s['auc']:.3f}  待ってよい {s['wait']:.0%}  "
                f"Brier {s['brier']:.4f}  対数損失 {s['logloss']:.4f}")
        if name != "基準: 雨＋風":
            (a_lo, w_lo, b_lo), (a_hi, w_hi, b_hi) = boot_diff(d, y, preds["基準: 雨＋風"], p)
            line += (f"\n  {'':28} 差: AUC［{a_lo:+.3f}, {a_hi:+.3f}］ 待ってよい［{w_lo:+.0%}, {w_hi:+.0%}］"
                     f" Brier［{b_lo:+.4f}, {b_hi:+.4f}］")
        print(line)

    print("\n== B. 地方ごとの偏り（予測の合計 − 実際の被害ありの数。0 に近いほど良い。正は出しすぎ、負は少なすぎ）")
    pick = ["基準: 雨＋風", "＋緯度＋経度", "＋地方（8 区分）", "＋都道府県（47、正則化）"]
    t = region_table(d, y, {k: preds[k] for k in pick})
    print(t.to_string(index=False, float_format=lambda v: f"{v:+.1f}"))
    for k in pick:
        print(f"  地方ごとのずれの二乗和 {k}: {(t[k] ** 2).sum():.1f}")

    print("\n== C. 地方を丸ごと抜いて当てる（知らない土地に持っていけるか。カテゴリ変数は使えないので数値だけ）")
    for name in ["基準: 雨＋風", "＋緯度", "＋緯度＋経度", "＋緯度×雨（閾値が南北で変わる）",
                 "勾配ブースティング 雨＋風", "勾配ブースティング 雨＋風＋緯度経度"]:
        cols, cat, kind = MODELS[name]
        p = cv(d, y, cols, cat, kind, d.region.values)
        s = scores(y, p)
        print(f"  {name:28} AUC {s['auc']:.3f}  待ってよい {s['wait']:.0%}  Brier {s['brier']:.4f}")

    print("\n== E. 特殊な県を外しても効くか（沖縄は 8〜9 月に稲がほぼない。東京・神奈川・大阪・奈良は田が少なく 100 ha に届きにくい）")
    for drop in (["沖縄"], ["沖縄", "東京", "神奈川", "大阪", "奈良"]):
        e = d[~d.pref.isin(drop)].reset_index(drop=True)
        ye = e.damaged.astype(int).values
        ps = {}
        print(f"  除外: {'・'.join(drop)}")
        for name in ["基準: 雨＋風", "＋緯度＋経度", "＋都道府県（47、正則化）", "勾配ブースティング 雨＋風＋緯度経度"]:
            cols, cat, kind = MODELS[name]
            ps[name] = cv(e, ye, cols, cat, kind, e.tid.values)
            s = scores(ye, ps[name])
            line = f"    {name:26} AUC {s['auc']:.3f}  待ってよい {s['wait']:.0%}  Brier {s['brier']:.4f}"
            if name != "基準: 雨＋風":
                lo, hi = boot_diff(e, ye, ps["基準: 雨＋風"], ps[name])
                line += f"  差: AUC［{lo[0]:+.3f}, {hi[0]:+.3f}］ Brier［{lo[2]:+.4f}, {hi[2]:+.4f}］"
            print(line)

    print("\n== D. 全データで当てはめた係数（標準化後。雨＋風＋緯度＋経度）")
    cols = BASE + ["lat", "lon"]
    m = logit().fit(d[cols].values, y)
    for c, w in zip(cols, m[-1].coef_[0]):
        print(f"  {c:14} {w:+.2f}")
    mp = logit("pref")(BASE).fit(d[BASE + ["pref"]], y)
    cp = pd.Series(mp[-1].coef_[0], index=mp[0].get_feature_names_out())
    cp = cp[cp.index.str.startswith("c__")].sort_values()
    cp.index = cp.index.str.replace("c__pref_", "")
    print("  都道府県の係数（雨＋風＋都道府県。負は同じ雨風でも被害が出にくい県）")
    print("    低い: " + "、".join(f"{k} {v:+.2f}" for k, v in cp.head(8).items()))
    print("    高い: " + "、".join(f"{k} {v:+.2f}" for k, v in cp.tail(8).items()))
    print(f"    茨城 {cp['茨城']:+.2f}、千葉 {cp['千葉']:+.2f}")
    pd.DataFrame({"pref": d.pref, "region": d.region, "tid": d.tid, "damaged": y,
                  **{f"pred_{k}": v for k, v in preds.items()}}).to_csv(
        "results/japan_location_predictions.csv", index=False)


if __name__ == "__main__":
    main()
