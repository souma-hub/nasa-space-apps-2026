# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pandas", "xlrd", "openpyxl"]
# ///
"""農林水産省「農作物災害種類別被害統計（被害応急調査結果）」から、災害ごとの茨城・千葉の水稲被害を集める。

各表は 1 つの災害（例:「台風第 7 号の風水害」）について、被害があった都道府県の行だけを持つ。
茨城・千葉の行がない災害は「その県では被害の報告なし」と読める（倒伏の閾値を決めるための「なし」側）。
出典: 農林水産省「作物統計調査 被害調査」（e-Stat）。出力は data/disaster_damage.csv。
"""
import argparse
import io
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402
import pandas as pd  # noqa: E402

SEARCH = "https://www.e-stat.go.jp/stat-search/files"
# e-Stat の分類: 作物統計調査 > 被害調査。tclass3 は公表年ごとの一覧
CLASS = {"toukei": "00500215", "tstat": "000001013427", "cycle": 7,
         "tclass1": "000001032308", "tclass2": "000001032935", "tclass4val": 0}
DOWNLOAD = "https://www.e-stat.go.jp/stat-search/file-download"
QUERY = "農作物災害種類別被害統計"
PREFS = ["茨城", "千葉"]
ALL_PREFS = ["北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木", "群馬", "埼玉",
             "千葉", "東京", "神奈川", "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡",
             "愛知", "三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山", "鳥取", "島根", "岡山",
             "広島", "山口", "徳島", "香川", "愛媛", "高知", "福岡", "佐賀", "長崎", "熊本", "大分",
             "宮崎", "鹿児島", "沖縄"]
RICE = re.compile(r"^(水稲|水陸稲)$")
ERA = {"平成": 1988, "令和": 2018}


def list_ids(c, only=None):
    """被害調査の公表年ごとの一覧（tclass3）を全部たどって、ファイル ID を集める。"""
    r = c.get(SEARCH, params={k: v for k, v in CLASS.items() if k != "tclass4val"})
    classes = list(dict.fromkeys(re.findall(r"tclass3=(\d+)", r.text)))
    if only:
        classes = [x for x in classes if x in only]
    ids = []
    for t3 in classes:
        for page in range(1, 50):
            r = c.get(SEARCH, params={**CLASS, "tclass3": t3, "layout": "datalist", "page": page})
            new = [i for i in dict.fromkeys(re.findall(r"statInfId=(\d+)", r.text)) if i not in ids]
            time.sleep(0.4)
            if not new:
                break
            ids += new
    return ids


def clean(x):
    return re.sub(r"\s", "", str(x)) if str(x) != "nan" else ""


def num(x):
    m = re.match(r"-?\d+(?:\.\d+)?", clean(x).replace(",", ""))
    return float(m.group(0)) if m else 0.0  # 「-」「…」は 0 とみなす


def parse_sheet(df, prefs=PREFS):
    """1 枚のシートから (年, 災害名, 水稲の列があるか, {県: 水稲被害面積 ha}) を返す。災害の表でなければ None。"""
    raw = [str(v).strip() for v in df.iloc[:12].values.ravel() if str(v) != "nan"]
    top = [clean(v) for v in raw]
    # 表番号（表１－19 など）の後ろの空白で区切って災害名を取る（空白を消すと月の数字とくっつくため）
    title = next((m.group(1) for t in raw
                  if (m := re.match(r"^表\s*[\d０-９]+\s*[－\-]\s*[\d０-９]+[\s\u3000]+(.+)$", t))), None)
    yr = next((re.search(r"(平成|令和)(\d+|元)年", t) for t in top if re.search(r"(平成|令和)(\d+|元)年", t)), None)
    if not title or not yr:
        return None
    year = ERA[yr.group(1)] + (1 if yr.group(2) == "元" else int(yr.group(2)))
    # 大きな災害（台風第15号など）は「２ 台風第15号による農作物被害」の行に災害名があり、
    # 表題は「類別被害概況…」のように共通なので、災害名の行を優先する
    ev = next((t for t in raw if "による農作物被害" in t), None)
    table = clean(title)
    name = clean(re.sub(r"^[\d０-９]+[\s\u3000]+", "", ev)) if ev else table
    # 作物名の行と、水稲の列を探す
    rice_col = None
    for i in range(min(20, len(df))):
        for j, v in enumerate(df.iloc[i].tolist()):
            if RICE.match(clean(v)):
                rice_col = j
                break
        if rice_col is not None:
            break
    out = {}
    for _, row in df.iterrows():
        cells = [clean(v) for v in row.tolist()]
        for k, v in enumerate(cells):
            if v in prefs:
                out[v] = num(row.iloc[rice_col]) if rice_col is not None else float("nan")
    return year, name, table, rice_col is not None, out


def download(c, sid, cache):
    """ファイルを取る。data/estat_cache に保存し、2 回目からはそれを使う。接続エラーは再試行する。"""
    f = cache / f"{sid}.bin"
    if f.exists():
        return f.read_bytes()
    for i in range(5):
        try:
            r = c.get(DOWNLOAD, params={"statInfId": sid, "fileKind": 0})
            if 400 <= r.status_code < 500:  # 存在しない・データベース形式などは再試行しない
                return None
            r.raise_for_status()
            f.write_bytes(r.content)
            time.sleep(0.4)
            return r.content
        except httpx.HTTPError as e:
            print(f"  {sid} 再試行 {i + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** i)
    return None


def main():
    p = argparse.ArgumentParser(description="災害ごとの水稲被害（茨城・千葉）を集める")
    p.add_argument("--only", nargs="*", help="tclass3 を限定（試験用）")
    p.add_argument("--all-prefs", action="store_true", help="全都道府県を抜き出す（全国モデル用）")
    p.add_argument("--out", default="data/disaster_damage.csv")
    a = p.parse_args()
    rows = []
    prefs = ALL_PREFS if a.all_prefs else PREFS
    cache = Path("data/estat_cache")
    cache.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        for i in range(5):
            try:
                ids = list_ids(c, a.only)
                break
            except httpx.HTTPError as e:
                print(f"  一覧の再試行 {i + 1}: {e}", file=sys.stderr)
                time.sleep(2 ** i)
        print(f"表のファイル: {len(ids)} 個", flush=True)
        for n, sid in enumerate(ids, 1):
            content = download(c, sid, cache)
            if content is None:
                continue
            try:
                sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
            except Exception:
                continue
            for df in sheets.values():
                got = parse_sheet(df, prefs)
                if not got:
                    continue
                year, name, table, has_rice, vals = got
                for pref in prefs:
                    rows.append({"year": year, "disaster": name, "table": table, "pref": pref,
                                 "listed": pref in vals, "table_has_rice": has_rice,
                                 "rice_area_ha": vals.get(pref, 0.0), "statInfId": sid})
            if n % 25 == 0:
                print(f"  {n} / {len(ids)}", flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["year", "disaster", "table", "pref"])
    out = Path(a.out)
    out.parent.mkdir(exist_ok=True)
    df.sort_values(["year", "disaster", "pref"]).to_csv(out, index=False)
    print(f"保存: {out}（災害 {df[['year', 'disaster']].drop_duplicates().shape[0]} 件）")


if __name__ == "__main__":
    main()
