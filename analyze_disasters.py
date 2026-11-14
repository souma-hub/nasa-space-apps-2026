# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy", "pandas", "scipy", "scikit-learn"]
# ///
"""嵐ごとに、農水省の災害統計（茨城・千葉の水稲被害面積）を正解として、気象との関係を調べる。

1. 気象庁ベストトラックで、各台風が関東南部（35.9N, 140.2E）に最も近づいた日時を求める
2. 災害統計の災害名（台風第◯号、◯月◯日〜◯日の◯害）を日付に直す
3. analyze_episodes.py の嵐（data/episodes.csv）と日付で突き合わせ、水稲被害面積を付ける。
   災害統計が対象とする年に、どの災害にも当たらない嵐は「被害の報告なし（0 ha）」とする
4. 被害あり／なしで、雨（アメダス・NASA IMERG・NASA POWER）と最大瞬間風速を比べ、
   ロジスティック回帰（雨・風・雨×風）を年単位の交差検証で比べる

注意: 統計の「水稲被害」は風水害の合計で、倒伏だけではない。
"""
import io
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

BST = "https://www.jma.go.jp/jma/jma-eng/jma-center/rsmc-hp-pub-eg/Besttracks/bst_all.zip"
SITE = (35.9, 140.2)
NEAR_KM = 500
Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def best_track(cache=Path("data/bst_all.txt")):
    if not cache.exists():
        z = zipfile.ZipFile(io.BytesIO(httpx.get(BST, timeout=120).content))
        cache.write_bytes(z.read("bst_all.txt"))
    rows, cur = [], None
    for line in cache.read_text().splitlines():
        if line.startswith("66666"):
            cur = line[6:10]  # YYNN
            continue
        f = line.split()
        if cur is None or len(f) < 5:
            continue
        t = pd.to_datetime(f[0], format="%y%m%d%H")
        lat, lon = int(f[3]) / 10, int(f[4]) / 10
        rows.append((cur, t, lat, lon))
    b = pd.DataFrame(rows, columns=["id", "time", "lat", "lon"])
    la, lo = np.radians(b.lat), np.radians(b.lon)
    sla, slo = np.radians(SITE[0]), np.radians(SITE[1])
    b["km"] = 6371 * np.arccos(np.clip(np.sin(la) * np.sin(sla)
                                       + np.cos(la) * np.cos(sla) * np.cos(lo - slo), -1, 1))
    near = b.loc[b.groupby("id").km.idxmin()].copy()
    near["year"] = near.time.dt.year
    near["num"] = near.id.str[2:].astype(int)
    near["jst"] = near.time + pd.Timedelta(hours=9)
    return near[["year", "num", "jst", "km"]]


def disaster_dates(name, year, bst):
    """災害名 → (開始日, 終了日) のリスト。台風は最接近日の前後 1 日。"""
    s = name.translate(Z2H)
    out = []
    for n in re.findall(r"台風第(\d+)号", s):
        r = bst[(bst.year == year) & (bst.num == int(n))]
        if len(r):
            d = r.iloc[0].jst.normalize()
            out.append((d - pd.Timedelta(days=1), d + pd.Timedelta(days=1), r.iloc[0].km))
    m = re.search(r"(\d+)月(\d+)日(?:[～~〜-](?:(\d+)月)?(\d+)日)?", s)
    if not out and m:
        m1, d1 = int(m.group(1)), int(m.group(2))
        m2 = int(m.group(3) or m1)
        d2 = int(m.group(4) or d1)
        out.append((pd.Timestamp(year, m1, d1), pd.Timestamp(year, m2, d2), np.nan))
    return out


def main():
    bst = best_track()
    dd = pd.read_csv("data/disaster_damage.csv")
    years = sorted(dd.year.unique())
    # 災害ごとの茨城＋千葉の水稲被害面積（同じ災害の複数の表は最大を採る）
    dd["rice"] = np.where(dd.listed & dd.table_has_rice, dd.rice_area_ha.fillna(0), 0.0)
    dis = (dd.groupby(["year", "disaster", "pref"]).rice.max()
             .groupby(level=[0, 1]).sum().reset_index())
    recs = []
    for r in dis.itertuples():
        for s, e, km in disaster_dates(r.disaster, r.year, bst):
            recs.append({"year": r.year, "disaster": r.disaster, "start": s, "end": e,
                         "km": km, "rice_ha": r.rice})
    dis = pd.DataFrame(recs)
    print(f"災害統計の対象年: {years[0]}〜{years[-1]}（{len(years)} 年）、日付が付いた災害 {len(dis)} 件")

    ds = pd.read_csv("data/dataset.csv", parse_dates=["date"])
    ep = pd.read_csv("data/episodes.csv", parse_dates=["start", "end"])
    ep = ep[ep.start.dt.year.isin(years)].copy()
    # 嵐ごとに IMERG と POWER の雨の合計も付ける
    for col, src in (("imerg", "imerg_mean"), ("power", "rain_sum")):
        ep[col] = [ds[(ds.date >= s) & (ds.date <= e + pd.Timedelta(days=1))][src].sum()
                   for s, e in zip(ep.start, ep.end)]
    hit, names = [], []
    for s, e in zip(ep.start, ep.end):
        m = dis[(dis.start <= e + pd.Timedelta(days=1)) & (dis.end >= s - pd.Timedelta(days=1))]
        hit.append(m.rice_ha.sum())
        names.append(" / ".join(sorted(set(m.disaster)))[:40])
    ep["rice_ha"], ep["disaster"] = hit, names
    ep["damaged"] = (ep.rice_ha > 0).astype(int)
    ep.to_csv("data/episodes_damage.csv", index=False)

    pos, neg = ep[ep.damaged == 1], ep[ep.damaged == 0]
    print(f"嵐 {len(ep)} 個: 水稲被害あり {len(pos)} / 報告なし {len(neg)}\n")
    print(ep.sort_values("rice_ha", ascending=False).head(15)[
        ["start", "end", "disaster", "rice_ha", "gust", "rain", "imerg", "power"]].to_string(
        index=False, float_format="%.0f"))

    print("\n== 被害ありの嵐 vs 報告なしの嵐（片側 Mann-Whitney）")
    for f, label in (("rain", "雨 アメダス"), ("imerg", "雨 NASA IMERG"), ("power", "雨 NASA POWER"),
                     ("rain_1h", "1時間雨量 アメダス"), ("gust", "最大瞬間風速"), ("wsmax", "最大風速")):
        u = stats.mannwhitneyu(pos[f].dropna(), neg[f].dropna(), alternative="greater")
        print(f"  {label:16}: あり中央値 {pos[f].median():6.1f} / なし {neg[f].median():6.1f}, p={u.pvalue:.4f}")

    print("\n== ロジスティック回帰（年ごとに 1 年抜いて当てる交差検証の AUC）")
    ep["lrain"] = np.log1p(ep.imerg)
    ep["lrain_am"] = np.log1p(ep.rain)
    models = {
        "雨だけ（IMERG）": ["lrain"],
        "風だけ": ["gust"],
        "雨＋風": ["lrain", "gust"],
        "雨＋風＋雨×風": ["lrain", "gust", "rxg"],
        "雨だけ（アメダス）": ["lrain_am"],
    }
    ep["rxg"] = ep.lrain * ep.gust
    yrs = ep.start.dt.year
    for name, cols in models.items():
        x = ep[cols].fillna(ep[cols].median()).values
        y = ep.damaged.values
        pred = np.full(len(y), np.nan)
        for yr in yrs.unique():
            tr, te = (yrs != yr).values, (yrs == yr).values
            if y[tr].sum() == 0:
                continue
            sc = StandardScaler().fit(x[tr])
            m = LogisticRegression(C=1.0).fit(sc.transform(x[tr]), y[tr])
            pred[te] = m.predict_proba(sc.transform(x[te]))[:, 1]
        ok = ~np.isnan(pred)
        sc = StandardScaler().fit(x)
        full = LogisticRegression(C=1.0).fit(sc.transform(x), y)
        coef = ", ".join(f"{c}={w:+.2f}" for c, w in zip(cols, full.coef_[0]))
        print(f"  {name:14}: AUC {roc_auc_score(y[ok], pred[ok]):.2f}  係数（標準化） {coef}")


if __name__ == "__main__":
    main()
