# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pandas", "numpy", "xarray", "netcdf4"]
# ///
"""全国版の倒伏予測のための「都道府県 × 台風」の学習用データを作る。

茨城・千葉と同じ手順（被害 → データ解析）を 47 都道府県に広げる。
1. 気象庁ベストトラック（data/bst_all.txt）で、2004〜2021 年の 8〜9 月に、
   都道府県の代表座標から 500 km 以内に近づいた台風を選ぶ（経路は 1 時間ごとに線形補間して最接近を求める）
2. 農水省「農作物災害種類別被害統計」（data/disaster_damage_all.csv、fetch_disaster_damage.py --all-prefs）
   の災害名から台風番号を取り出し、その都道府県の水稲被害面積 rice_ha を付ける。damaged = rice_ha >= 100
3. 気象（すべて NASA）:
   - rain_4d_imerg: GPM IMERG 日別（Final）。最接近日の前 2 日〜後 1 日の合計、代表座標の 3×3 格子の平均
   - eff_heat_may1: NASA POWER の日平均気温 T2M から、5 月 1 日〜最接近日の有効積算温度（T2M − 10℃ の合計）
   - ws10m_max_3d: NASA POWER の日最大風速 WS10M_MAX（最接近日の前 1 日〜後 1 日の最大）
出力は data/japan_typhoon_dataset.csv。

注意:
- IMERG の日は UTC の日（日本時間 9 時〜翌 9 時）。最接近日（日本時間）の日付をそのまま当てている
- 代表座標は県庁所在地で、県内の水田の中心とは限らない（北海道など広い県では特に粗い）
"""
import argparse
import io
import re
import sys
import tempfile
import threading
import time
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

# 都道府県の代表座標（県庁所在地、度）。
# 根拠: 国土地理院「都道府県庁所在地の経緯度」の値を小数第 2〜4 位で丸めたもの（厳密でなくてよい用途）
PREF_COORDS = {
    "北海道": (43.064, 141.347), "青森": (40.824, 140.740), "岩手": (39.704, 141.153),
    "宮城": (38.269, 140.872), "秋田": (39.719, 140.103), "山形": (38.241, 140.363),
    "福島": (37.750, 140.468), "茨城": (36.342, 140.447), "栃木": (36.566, 139.884),
    "群馬": (36.391, 139.061), "埼玉": (35.857, 139.649), "千葉": (35.605, 140.123),
    "東京": (35.690, 139.692), "神奈川": (35.448, 139.643), "新潟": (37.902, 139.024),
    "富山": (36.695, 137.211), "石川": (36.594, 136.626), "福井": (36.065, 136.222),
    "山梨": (35.664, 138.568), "長野": (36.651, 138.181), "岐阜": (35.391, 136.722),
    "静岡": (34.977, 138.383), "愛知": (35.180, 136.907), "三重": (34.730, 136.509),
    "滋賀": (35.004, 135.868), "京都": (35.021, 135.756), "大阪": (34.686, 135.520),
    "兵庫": (34.691, 135.183), "奈良": (34.685, 135.833), "和歌山": (34.226, 135.168),
    "鳥取": (35.504, 134.238), "島根": (35.472, 133.051), "岡山": (34.662, 133.935),
    "広島": (34.396, 132.459), "山口": (34.186, 131.471), "徳島": (34.066, 134.559),
    "香川": (34.340, 134.043), "愛媛": (33.842, 132.766), "高知": (33.560, 133.531),
    "福岡": (33.606, 130.418), "佐賀": (33.249, 130.299), "長崎": (32.745, 129.874),
    "熊本": (32.790, 130.742), "大分": (33.238, 131.613), "宮崎": (31.911, 131.424),
    "鹿児島": (31.560, 130.558), "沖縄": (26.213, 127.681),
}

BST = "https://www.jma.go.jp/jma/jma-eng/jma-center/rsmc-hp-pub-eg/Besttracks/bst_all.zip"
FIRST_YEAR, LAST_YEAR = 2004, 2021
NEAR_KM = 500
DAMAGED_HA = 100

# GPM IMERG 日別（Final, V07）。0.1° 格子の添字: lon = -179.95 + 0.1 i, lat = -89.95 + 0.1 j
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
IMERG_FINAL = "C2723754864-GES_DISC"  # 2025-09-30 まで。2004〜2021 年はすべてこちら
LON_I = (3020, 3259)  # 122.05〜145.95E
LAT_J = (1140, 1359)  # 24.05〜45.95N
CE = (f"dap4.ce=/precipitation[0:1:0][{LON_I[0]}:1:{LON_I[1]}][{LAT_J[0]}:1:{LAT_J[1]}]"
      .replace("[", "%5B").replace("]", "%5D"))
READ_LOCK = threading.Lock()  # netCDF/HDF5 の読み込みは同時に行うと固まるので 1 つずつ（fetch_imerg.py と同じ）

POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"


# ---------------------------------------------------------------- ベストトラック
def read_tracks(path=Path("data/bst_all.txt")):
    """ベストトラックの全経路点（UTC）を読み、台風ごとに 1 時間おきへ線形補間して返す。"""
    if not path.exists():
        z = zipfile.ZipFile(io.BytesIO(httpx.get(BST, timeout=120).content))
        path.write_bytes(z.read("bst_all.txt"))
    rows, cur = [], None
    for line in path.read_text().splitlines():
        if line.startswith("66666"):
            cur = line[6:10]  # YYNN（NN が台風番号）
            continue
        f = line.split()
        if cur is None or len(f) < 5:
            continue
        t = pd.to_datetime(f[0], format="%y%m%d%H")
        if t.year > 2050:  # 2 桁の年: 1951〜1968 年が 20xx 年と読まれるのを直す
            t = t.replace(year=t.year - 100)
        rows.append((cur, t, int(f[2]), int(f[3]) / 10, int(f[4]) / 10))
    b = pd.DataFrame(rows, columns=["id", "time", "grade", "lat", "lon"])
    b = b[(b.time.dt.year >= FIRST_YEAR - 1) & (b.time.dt.year <= LAST_YEAR + 1)]
    out = []
    for sid, g in b.groupby("id"):
        g = g.drop_duplicates("time").set_index("time").sort_index()
        h = g[["lat", "lon"]].resample("1h").interpolate()
        h["grade"] = g["grade"].reindex(h.index).ffill()
        h["id"] = sid
        out.append(h.reset_index())
    t = pd.concat(out, ignore_index=True)
    # 台風番号の年は経路の最初の時刻の年（YY は 2 桁なので、経路から決める）
    t["year"] = t.groupby("id").time.transform("min").dt.year
    t["num"] = t.id.str[2:].astype(int)
    return t


def haversine_km(lat1, lon1, lat2, lon2):
    la1, lo1, la2, lo2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def pref_typhoon_pairs(tracks):
    """都道府県ごとに、各台風の最接近（距離・日本時間）を求め、8〜9 月・500 km 以内を残す。"""
    tr = tracks[(tracks.year >= FIRST_YEAR) & (tracks.year <= LAST_YEAR)]
    rows = []
    for pref, (lat, lon) in PREF_COORDS.items():
        d = tr.assign(km=haversine_km(tr.lat.values, tr.lon.values, lat, lon))
        near = d.loc[d.groupby("id").km.idxmin()]
        for _, r in near.iterrows():
            jst = r.time + pd.Timedelta(hours=9)
            if r.km <= NEAR_KM and jst.month in (8, 9):
                rows.append({"year": int(r.year), "typhoon_num": int(r.num), "pref": pref,
                             "lat": lat, "lon": lon, "closest_km": round(float(r.km), 1),
                             "closest_time_jst": jst, "grade_at_closest": int(r.grade)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 被害ラベル
def typhoon_numbers(text):
    """災害名から台風番号を取り出す。全角数字、「台風第７号、第11号及び第９号」「台風第15、16及び18号」に対応。"""
    s = unicodedata.normalize("NFKC", str(text))
    nums = []
    for m in re.finditer(r"台風((?:第?\d+号?(?:、|,|及び|・|と)?)+)", s):
        part = m.group(1)
        part = part[:part.rfind("号") + 1]  # 最後の「号」まで（「及び8月11日からの大雨」の 8 を拾わない）
        nums += [int(x) for x in re.findall(r"\d+", part)]
    return list(dict.fromkeys(nums))


def damage_labels(path=Path("data/disaster_damage_all.csv")):
    """(year, typhoon_num, pref) → rice_ha, shared_table, 出典の災害名。

    同じ災害が複数の表（類別・作物別など）に載るので、都道府県ごとに水稲の列がある表の最大値をとる。
    """
    d = pd.read_csv(path)
    d["event"] = d.disaster.fillna("") + " / " + d.table.fillna("")
    d["nums"] = d.event.map(typhoon_numbers)
    d = d[d.nums.str.len() > 0]
    # 災害（年 + 災害名 + 台風を含む方の表名）ごとに、都道府県の水稲被害面積
    d["key"] = np.where(d.table.str.contains("台風"), d.table, d.disaster)
    g = (d[d.table_has_rice].groupby(["year", "key", "pref"])
         .agg(rice_ha=("rice_area_ha", "max")).reset_index())
    nums = d.drop_duplicates(["year", "key"]).set_index(["year", "key"]).nums
    g["nums"] = [nums[(y, k)] for y, k in zip(g.year, g.key)]
    g["shared_table"] = g.nums.str.len() > 1
    g = g.explode("nums").rename(columns={"nums": "typhoon_num"})
    g["typhoon_num"] = g.typhoon_num.astype(int)
    # 同じ台風が 2 つの災害（単独の表と合同の表など）に出るときは被害の大きい方
    g = g.sort_values("rice_ha", ascending=False).drop_duplicates(["year", "typhoon_num", "pref"])
    # 台風の表はあるが水稲の列がない災害（沖縄だけの小さな表など）も「表あり」として記録する
    has_table = d.drop_duplicates(["year", "key"]).explode("nums")
    has_table = set(zip(has_table.year, has_table.nums.astype(int)))
    return g.rename(columns={"key": "damage_source"}), has_table


# ---------------------------------------------------------------- IMERG
def imerg_urls(c, days):
    """CMR から、必要な日の OPeNDAP URL を {日付: URL} で返す（年ごとに 8〜10 月をまとめて問い合わせる）。"""
    out = {}
    for y in sorted({d[:4] for d in days}):
        page = 1
        while True:
            r = c.get(CMR, params={"collection_concept_id": IMERG_FINAL, "page_size": 200,
                                   "page_num": page,
                                   "temporal": f"{y}-07-25T00:00:00Z,{y}-10-05T23:59:59Z"})
            e = r.json()["feed"]["entry"]
            for g in e:
                u = next((lk["href"] for lk in g["links"]
                          if "opendap.earthdata.nasa.gov" in lk.get("href", "")), None)
                if u:
                    out[g["time_start"][:10]] = u
            if len(e) < 200:
                break
            page += 1
    return out


def fetch_imerg_day(c, day, url, cache):
    """日本全体（24〜46N, 122〜146E）の 1 日分を切り出し、mm/day の配列 [lon, lat] で保存する。"""
    f = cache / f"{day}.npy"
    if f.exists():
        return True
    for i in range(4):
        try:
            r = c.get(f"{url}.dap.nc4?{CE}")
            r.raise_for_status()
            with READ_LOCK, tempfile.NamedTemporaryFile(suffix=".nc4") as tmp:
                tmp.write(r.content)
                tmp.flush()
                d = xr.open_dataset(tmp.name)
                v = d["precipitation"].values.astype("float32")[0]
                units = d["precipitation"].attrs.get("units", "")
                d.close()
            v[v < 0] = np.nan
            if "hr" in units:  # 単位が mm/hr（1 日の平均強度）なら mm/day に直す
                v = v * 24
            np.save(f, v)
            return True
        except Exception as e:
            print(f"  IMERG {day} 再試行 {i + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** i)
    return False


def imerg_point(arr, lat, lon):
    """代表座標を含む格子を中心に 3×3 格子の平均（mm/day）。"""
    i = int(round((lon + 179.95) / 0.1)) - LON_I[0]
    j = int(round((lat + 89.95) / 0.1)) - LAT_J[0]
    return float(np.nanmean(arr[i - 1:i + 2, j - 1:j + 2]))


def add_imerg(df, workers):
    cache = Path("data/imerg_japan")
    cache.mkdir(parents=True, exist_ok=True)
    day0 = df.closest_time_jst.dt.normalize()
    need = sorted({(d + pd.Timedelta(days=k)).strftime("%Y-%m-%d") for d in day0 for k in (-2, -1, 0, 1)})
    todo = [d for d in need if not (cache / f"{d}.npy").exists()]
    print(f"IMERG: 必要な日 {len(need)}、未取得 {len(todo)}", flush=True)
    if todo:
        with httpx.Client(timeout=180, follow_redirects=True) as c:
            urls = imerg_urls(c, todo)
            jobs = [(d, urls[d]) for d in todo if d in urls]
            with ThreadPoolExecutor(workers) as ex:
                for n, _ in enumerate(ex.map(lambda j: fetch_imerg_day(c, *j, cache), jobs), 1):
                    if n % 50 == 0:
                        print(f"  {n} / {len(jobs)}", flush=True)
    arrs = {}

    def get(day):
        if day not in arrs:
            f = cache / f"{day}.npy"
            arrs[day] = np.load(f) if f.exists() else None
        return arrs[day]

    vals = []
    for d, lat, lon in zip(day0, df.lat, df.lon):
        x = [get((d + pd.Timedelta(days=k)).strftime("%Y-%m-%d")) for k in (-2, -1, 0, 1)]
        vals.append(np.nan if any(a is None for a in x) else
                    round(sum(imerg_point(a, lat, lon) for a in x), 1))
    df["rain_4d_imerg"] = vals
    return df


# ---------------------------------------------------------------- NASA POWER
def power_pref(pref, lat, lon, cache):
    """NASA POWER の日別 T2M と WS10M_MAX（2004〜2021 年の 5〜9 月）。都道府県ごとにキャッシュする。"""
    f = cache / f"{pref}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["date"]).set_index("date")
    for i in range(5):
        try:
            r = httpx.get(POWER, params={"parameters": "T2M,WS10M_MAX", "community": "AG",
                                         "latitude": lat, "longitude": lon,
                                         "start": f"{FIRST_YEAR}0101", "end": f"{LAST_YEAR}1231",
                                         "format": "JSON"}, timeout=300)
            r.raise_for_status()
            break
        except httpx.HTTPError as e:
            print(f"  POWER {pref} 再試行 {i + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** i)
    else:
        return None
    p = r.json()["properties"]["parameter"]
    d = pd.DataFrame({k: pd.Series(v) for k, v in p.items()})
    d.index = pd.to_datetime(d.index, format="%Y%m%d")
    d = d.replace(-999.0, np.nan)
    d = d[(d.index.month >= 5) & (d.index.month <= 9)].rename_axis("date")
    d.to_csv(f)
    return d


def add_power(df):
    cache = Path("data/power_pref")
    cache.mkdir(parents=True, exist_ok=True)
    eff, ws = [], []
    pw = {}
    for pref in df.pref.unique():
        lat, lon = PREF_COORDS[pref]
        pw[pref] = power_pref(pref, lat, lon, cache)
        time.sleep(0.3)
    for _, r in df.iterrows():
        p = pw[r.pref]
        day = r.closest_time_jst.normalize()
        if p is None:
            eff.append(np.nan)
            ws.append(np.nan)
            continue
        t = p.loc[pd.Timestamp(day.year, 5, 1):day, "T2M"]
        # 欠損がある日は捨てずに前後で補間する（POWER の欠損はまれ）
        eff.append(round(float((t.interpolate() - 10).clip(lower=0).sum()), 1) if t.notna().any() else np.nan)
        w = p.loc[day - pd.Timedelta(days=1):day + pd.Timedelta(days=1), "WS10M_MAX"]
        ws.append(round(float(w.max()), 2) if w.notna().any() else np.nan)
    df["eff_heat_may1"] = eff
    df["ws10m_max_3d"] = ws
    return df


# ---------------------------------------------------------------- まとめ
def main():
    ap = argparse.ArgumentParser(description="都道府県 × 台風の学習用データを作る")
    ap.add_argument("--workers", type=int, default=4, help="IMERG を同時に取りに行く数")
    ap.add_argument("--out", default="data/japan_typhoon_dataset.csv")
    a = ap.parse_args()

    df = pref_typhoon_pairs(read_tracks())
    print(f"候補（都道府県 × 台風、8〜9 月・{NEAR_KM} km 以内）: {len(df)} 行", flush=True)

    lab, has_table = damage_labels()
    df = df.merge(lab[["year", "typhoon_num", "pref", "rice_ha", "shared_table", "damage_source"]],
                  on=["year", "typhoon_num", "pref"], how="left")
    df["stat_table"] = [(y, n) in has_table for y, n in zip(df.year, df.typhoon_num)]
    # 統計の表がない台風、表に載っていない都道府県は 0
    df["rice_ha"] = df.rice_ha.fillna(0.0)
    df["shared_table"] = df.shared_table.fillna(False).astype(bool)
    df["damage_source"] = df.damage_source.fillna("")
    df["damaged"] = df.rice_ha >= DAMAGED_HA
    df["doy"] = df.closest_time_jst.dt.day_of_year

    df = add_imerg(df, a.workers)
    df = add_power(df)

    cols = ["year", "typhoon_num", "pref", "lat", "lon", "closest_km", "closest_time_jst",
            "grade_at_closest", "doy", "rice_ha", "damaged", "shared_table", "stat_table",
            "damage_source", "rain_4d_imerg", "eff_heat_may1", "ws10m_max_3d"]
    df = df[cols].sort_values(["year", "typhoon_num", "closest_km"])
    df["closest_time_jst"] = df.closest_time_jst.dt.strftime("%Y-%m-%d %H:%M")
    out = Path(a.out)
    df.to_csv(out, index=False)

    # ---- 要約
    print(f"\n保存: {out}")
    print(f"行数: {len(df)}、都道府県: {df.pref.nunique()}、台風: "
          f"{df[['year', 'typhoon_num']].drop_duplicates().shape[0]}")
    print(f"damaged（水稲被害 {DAMAGED_HA} ha 以上）: {int(df.damaged.sum())} 行"
          f"（うち shared_table: {int((df.damaged & df.shared_table).sum())}）、"
          f"rice_ha > 0: {int((df.rice_ha > 0).sum())} 行")
    print(f"統計の表がある台風の行: {int(df.stat_table.sum())} / {len(df)}")
    print("\n年ごとの件数:")
    print(df.groupby("year").agg(rows=("pref", "size"), damaged=("damaged", "sum"),
                                 typhoons=("typhoon_num", "nunique")).to_string())
    print("\n欠損の数:")
    print(df.isna().sum()[lambda s: s > 0].to_string() or "なし")


if __name__ == "__main__":
    main()
