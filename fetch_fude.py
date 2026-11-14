# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv"]
# ///
"""農林水産省「筆ポリゴン」（2026 年度公開、ArcGIS Online 版）から、範囲内の田を GeoJSON で保存する。

出典: 農林水産省「筆ポリゴンデータ（2026年度公開）」。利用規約に従い、出典を明記して使う。
範囲検索で ID を集め、ID 指定でまとめて図形を取る（範囲検索で図形を直接返す問い合わせは 400 になるため）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

import httpx  # noqa: E402

LAYER = ("https://services8.arcgis.com/cW9ZoPyzxXOxrpu1/arcgis/rest/services/"
         "FudePolygonTemp_2026/FeatureServer/0/query")
PADDY = 100  # land_type: 100=田, 200=畑


def get(client, params, post=False):
    for i in range(4):
        try:
            r = (client.post(LAYER, data=params, timeout=120) if post
                 else client.get(LAYER, params=params, timeout=120))
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"])
            return d
        except (httpx.HTTPError, RuntimeError) as e:
            print(f"  再試行 {i + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** i)
    sys.exit("取得に失敗しました")


def main():
    p = argparse.ArgumentParser(description="筆ポリゴン（田）を取得")
    p.add_argument("--bbox", type=float, nargs=4, default=[140.15, 35.85, 140.40, 36.0],
                   metavar=("W", "S", "E", "N"))
    p.add_argument("--out", default="data/fude_paddy.geojson")
    p.add_argument("--chunk", type=int, default=250)
    a = p.parse_args()

    with httpx.Client() as c:
        ids = get(c, {
            "where": f"land_type={PADDY}", "geometry": ",".join(map(str, a.bbox)),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true", "f": "json",
        })["objectIds"]
        print(f"田の区画: {len(ids):,}")
        feats = []
        for i in range(0, len(ids), a.chunk):
            d = get(c, {
                "objectIds": ",".join(map(str, ids[i:i + a.chunk])),
                "outFields": "OBJECTID,polygon_uuid,local_government_cd,SHAPE__Area",
                "returnGeometry": "true", "outSR": 4326, "f": "geojson",
            }, post=True)
            feats += d["features"]
            print(f"  {len(feats):,} / {len(ids):,}", end="\r", flush=True)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"\n保存: {out}（{out.stat().st_size / 1e6:.1f} MB）")


if __name__ == "__main__":
    main()
