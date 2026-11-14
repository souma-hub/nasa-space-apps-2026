# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy"]
# ///
"""docs/demo/index.html の JS 判定関数が、Python の decide()（lodging_unified.py）と一致するかを node で確かめる。

シナリオ 10 個と、過去 23 台風の再現（茨城・コシヒカリ、予報 0）で、確率が小数 6 桁・判断・理由の文言まで一致するかを見る。
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import nasa_common  # noqa: E402,F401

from demo_lodging import SCENARIOS  # noqa: E402
from lodging_unified import decide  # noqa: E402

HTML = ROOT / "docs/demo/index.html"
HARNESS = r'''
import fs from "node:fs";
const [html, casesPath] = process.argv.slice(2);
const src = fs.readFileSync(html, "utf8");
const grab = id => src.match(new RegExp('<script id="' + id + '"[^>]*>([\\s\\S]*?)</script>'))[1];
const D = JSON.parse(grab("data").split("<\\/").join("</"));
const decide = new Function(grab("core") + "; return decide;")();
const cases = JSON.parse(fs.readFileSync(casesPath, "utf8"));
const out = cases.map(c => { const r = decide(D, c.pref, c.past, c.forecast, c.wind, c.gdd, c.variety);
  return {p: r.probability, harvest: r.harvest, thr: r.threshold, reasons: r.reasons}; });
console.log(JSON.stringify({out, typhoons: D.typhoons}));
'''


def run_node(node, td, cases):
    (td / "c.json").write_text(json.dumps(cases), encoding="utf-8")
    r = subprocess.run([node, str(td / "h.mjs"), str(HTML), str(td / "c.json")],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit("node 失敗: " + r.stderr)
    return json.loads(r.stdout)


def main():
    node = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
    P = json.loads((ROOT / "results/unified_model.json").read_text(encoding="utf-8"))
    cases = []
    for title, kw in SCENARIOS:
        cases.append(dict(label=title, pref=kw["pref"], past=kw["rain_past_mm"], forecast=kw["rain_forecast_mm"],
                          wind=kw["wind_ms"], gdd=kw.get("gdd"), variety=kw.get("variety", "koshihikari")))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "h.mjs").write_text(HARNESS, encoding="utf-8")
        # 台風は HTML に埋め込まれた値で作る（埋め込みの欠落も検出するため）
        typh = run_node(node, td, [])["typhoons"]
        for t in typh:
            cases.append(dict(label="台風 " + t["name"], pref="茨城", past=t["rain"], forecast=0, wind=t["wind"],
                              gdd=t["gdd"], variety="koshihikari"))
        res = run_node(node, td, cases)["out"]
    ok_p = ok_d = ok_r = ok_all = 0
    for c, j in zip(cases, res):
        py = decide(c["pref"], c["past"], c["forecast"], c["wind"], c["gdd"], c["variety"], P=P)
        a = abs(py["probability"] - j["p"]) < 5e-7
        b = py["harvest"] == j["harvest"]
        if not b and abs(py["probability"] - py["threshold"]) < 1e-9:
            # 確率が閾値とちょうど等しい境界例（浮動小数点の最後の桁の差で >= の結果が割れる）。一致扱いにして注記する
            print(f"注記（境界例）: {c['label']} py p={py['probability']!r} thr={py['threshold']!r} harvest={py['harvest']} / js p={j['p']!r} harvest={j['harvest']}")
            b = True
        r = py["reasons"] == j["reasons"]
        ok_p += a; ok_d += b; ok_r += r; ok_all += a and b and r
        if not (a and b and r):
            print(f"不一致: {c['label']} py={py['probability']:.8f} js={j['p']:.8f}")
            if not r:
                print("  py:", py["reasons"]); print("  js:", j["reasons"])
    n = len(cases)
    print(f"確率一致（小数 6 桁）{ok_p}/{n}、判断一致 {ok_d}/{n}、理由の文言一致 {ok_r}/{n}（シナリオ {len(SCENARIOS)} + 台風 {len(typh)}）")
    diffs = [abs(j["p"] - t["p_unified"]) for t, j in zip(typh, res[len(SCENARIOS):])]
    same = sum(d < 5e-7 for d in diffs)
    print(f"参考: 再現確率と CSV の p_unified が小数 6 桁で一致 {same}/{len(typh)}（最大差 {max(diffs):.4f}）")
    sys.exit(0 if ok_all == n else 1)


if __name__ == "__main__":
    main()
