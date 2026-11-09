# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv"]
# ///
"""APOD（今日の天文写真）を取得して表示する。

既定は新エンドポイント（science.nasa.gov の WordPress API、キー不要・形状は未検証）。
--legacy で旧 api.nasa.gov/planetary/apod（現在 HTTP 500 の見込み）を使う。
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# PEP 723 スクリプトから同フォルダの nasa_common を import できるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nasa_common import nasa_get, public_get, unescape  # noqa: E402

NEW_URL = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"
NONE = "(なし)"


def text_of(v) -> str | None:
    """文字列ならそのまま、WordPress 形式 {"rendered": ...} なら HTML タグを除いて返す。"""
    if isinstance(v, dict):
        v = v.get("rendered")
    if not isinstance(v, str) or not v.strip():
        return None
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", v)).strip())


def main() -> None:
    p = argparse.ArgumentParser(description="NASA APOD")
    p.add_argument("--date", help="YYYY-MM-DD（省略時は今日）")
    p.add_argument("--json", action="store_true", help="生JSONを整形出力")
    p.add_argument("--legacy", action="store_true", help="旧 api.nasa.gov/planetary/apod を使う（キー付き）")
    args = p.parse_args()

    if args.legacy:
        params = {"date": args.date} if args.date else {}
        data = nasa_get("/planetary/apod", params)
    else:
        url = NEW_URL
        if args.date:
            try:
                d = datetime.strptime(args.date, "%Y-%m-%d")
            except ValueError:
                sys.exit("エラー: --date は YYYY-MM-DD 形式で指定してください")
            url = f"{NEW_URL}/{d:%y%m%d}"
        data = public_get(url)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        data = {}

    title = text_of(data.get("title"))
    explanation = text_of(data.get("explanation")) or text_of(data.get("content")) or text_of(data.get("excerpt"))
    if explanation and explanation.startswith("Explanation:"):
        explanation = explanation.removeprefix("Explanation:").strip()
    fields = {
        "タイトル  ": title,
        "日付      ": data.get("date"),
        "media_type": data.get("media_type"),
        "url       ": unescape(data.get("url")),
        "hdurl     ": unescape(data.get("hdurl")),
    }
    # 想定キーがほぼ取れない場合は形状の違いを知らせる
    got = sum(1 for v in [*fields.values(), explanation] if v)
    if got <= 1:
        print("形状が想定と違うので --json で確認してください", file=sys.stderr)

    for label, v in fields.items():
        print(f"{label}: {v or NONE}")
    print(f"解説      : {explanation[:300] if explanation else NONE}")


if __name__ == "__main__":
    main()
