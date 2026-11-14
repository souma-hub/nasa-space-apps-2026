# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pandas", "xlrd"]
# ///
"""農林水産省「作物統計」の水稲被害（都道府県別）から、茨城・千葉の風水害の被害面積・被害量を集める。

各年産の表「水稲被害面積及び被害量（全国農業地域別・都道府県別）」を e-Stat で探して読む。
風水害の区分があるのは 2016 年産（平成 28 年産）まで。2017 年産からは被害種類が 6 区分になり、風水害がない。
出典: 農林水産省「作物統計調査」（e-Stat）。出力は data/maff_wind_damage.csv。
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
DOWNLOAD = "https://www.e-stat.go.jp/stat-search/file-download"
PREFS = ["茨城", "千葉"]


def candidates(c, n):
    ids = []
    for q, page in ((f"{n}年産水稲被害面積及び被害量 都道府県別", 1),
                    (f"{n}年産水稲の被害面積及び被害量 都道府県別", 1),
                    (f"{n}年産水稲被害面積及び被害量 都道府県別", 2)):
        r = c.get(SEARCH, params={"page": page, "query": q, "layout": "dataset",
                                  "metadata": 1, "data": 1})
        ids += [i for i in re.findall(r"statInfId=(\d+)", r.text) if i not in ids]
        time.sleep(0.5)
    return ids


def parse(content, n):
    """表なら {県: (風水害面積 ha, 風水害量 t, 作付に対する被害面積率…)} を返す。違えば None。"""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
    except Exception:
        return None
    head = " ".join(str(v) for v in df.iloc[:12].values.ravel())
    head = re.sub(r"\s", "", head)
    if not re.search(rf"(?<!\d){n}年産水稲の?被害", head) or "風水害" not in head:
        return None
    out = {}
    for _, row in df.iterrows():
        vals = [v for v in row.tolist() if str(v) != "nan"]
        names = [v for v in vals if isinstance(v, str) and v.strip() in PREFS]
        if not names:
            continue
        i = vals.index(names[0])
        nums = vals[i + 1:]
        # 並び: 県コード, 被害面積, 被害実面積, 被害量, 面積率, 実面積率, 被害率, 気象計(面積, 量), 風水害(面積, 量)
        try:
            out[names[0].strip()] = {
                "total_area": float(nums[1]), "total_t": float(nums[3]),
                "wind_area": float(nums[9]), "wind_t": float(nums[10]),
            }
        except (ValueError, IndexError):
            return None
    return out if len(out) == len(PREFS) else None


def main():
    p = argparse.ArgumentParser(description="水稲の風水害被害（茨城・千葉）を集める")
    p.add_argument("--first", type=int, default=2001)
    p.add_argument("--last", type=int, default=2016)
    p.add_argument("--out", default="data/maff_wind_damage.csv")
    a = p.parse_args()
    out = Path(a.out)
    old = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["year"])
    rows = old.to_dict("records")
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        for year in range(a.first, a.last + 1):
            if year in set(old["year"]):
                continue
            n = year - 1988  # 平成
            got = None
            for sid in candidates(c, n)[:16]:
                r = c.get(DOWNLOAD, params={"statInfId": sid, "fileKind": 0})
                time.sleep(0.5)
                got = parse(r.content, n)
                if got:
                    break
            if not got:
                print(f"  {year}（平成{n}年産）: 見つからず", flush=True)
                continue
            for pref, v in got.items():
                rows.append({"year": year, "pref": pref, "statInfId": sid, **v})
            print(f"  {year}（平成{n}年産）: " + ", ".join(
                f"{k} 風水害 {v['wind_area']:.0f} ha / {v['wind_t']:.0f} t" for k, v in got.items()),
                flush=True)
    out.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).sort_values(["year", "pref"]).to_csv(out, index=False)
    print(f"保存: {out}（{len(rows)} 行）")


if __name__ == "__main__":
    main()
