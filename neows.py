# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv"]
# ///
"""NeoWs feed: 期間内の接近小惑星を、最接近距離の近い順に上位10件表示する。"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# PEP 723 スクリプトから同フォルダの nasa_common を import できるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import nasa_get  # noqa: E402

FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"


def main() -> None:
    p = argparse.ArgumentParser(description="NASA NeoWs")
    p.add_argument("--start", help="開始日 YYYY-MM-DD（省略時は今日）")
    p.add_argument("--days", type=int, default=7, help="日数 1〜7（デフォルト7）")
    args = p.parse_args()

    if not 1 <= args.days <= 7:
        sys.exit("エラー: --days は 1〜7 です（feed API の上限が7日のため）")
    try:
        start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else date.today()
    except ValueError:
        sys.exit("エラー: --start は YYYY-MM-DD 形式で指定してください")
    # end_date は含まれるので days-1 日後
    end = start + timedelta(days=args.days - 1)

    data = nasa_get(FEED_URL, {"start_date": start.isoformat(), "end_date": end.isoformat()})

    # 全件を平らにして、最接近距離(km)でソート
    rows = []
    for neos in data.get("near_earth_objects", {}).values():
        for neo in neos:
            ca = neo["close_approach_data"][0]
            dia = neo["estimated_diameter"]["meters"]
            rows.append((
                neo["name"],
                ca["close_approach_date"],
                float(ca["miss_distance"]["kilometers"]),
                dia["estimated_diameter_min"],
                dia["estimated_diameter_max"],
                float(ca["relative_velocity"]["kilometers_per_second"]),
                "危険" if neo["is_potentially_hazardous_asteroid"] else "-",
            ))
    rows.sort(key=lambda r: r[2])

    print(f"期間: {start} 〜 {end}  全 {len(rows)} 件中 上位10件")
    header = ["名前", "接近日", "距離(km)", "直径(m) min〜max", "速度(km/s)", "危険"]
    body = [
        [n, d, f"{km:,.0f}", f"{lo:,.1f}〜{hi:,.1f}", f"{v:.2f}", h]
        for n, d, km, lo, hi, v, h in rows[:10]
    ]
    widths = [max(len(r[i]) for r in [header, *body]) for i in range(len(header))]

    def fmt(r: list[str]) -> str:
        # 数値列は右寄せ、他は左寄せ
        return "  ".join(
            c.rjust(w) if i in (2, 4) else c.ljust(w)
            for i, (c, w) in enumerate(zip(r, widths))
        )

    print(fmt(header))
    print("  ".join("-" * w for w in widths))
    for r in body:
        print(fmt(r))


if __name__ == "__main__":
    main()
