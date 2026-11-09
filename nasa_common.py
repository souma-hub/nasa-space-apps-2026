"""NASA API 共通処理: API キー読み込みと GET ヘルパー。"""
import os
import sys
import html

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.nasa.gov"

# Windows（cp932）環境でも日本語や特殊文字で落ちないよう、出力を UTF-8 に固定する
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_api_key() -> str:
    """環境変数 NASA_API_KEY → .env → DEMO_KEY の順でキーを決める。"""
    load_dotenv()  # 既存の環境変数は上書きしない
    key = os.environ.get("NASA_API_KEY")
    if not key:
        print(
            "警告: NASA_API_KEY が未設定のため DEMO_KEY を使います（レート制限が厳しい）",
            file=sys.stderr,
        )
        return "DEMO_KEY"
    return key


def nasa_get(path: str, params: dict | None = None) -> dict:
    """api.nasa.gov に GET してJSONを返す。失敗時は stderr に出して終了。"""
    params = dict(params or {})
    params["api_key"] = load_api_key()
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    return _get_json(url, params)


def public_get(url: str, params: dict | None = None):
    """キー不要の公開エンドポイントに GET してJSONを返す。失敗時は stderr に出して終了。"""
    return _get_json(url, dict(params or {}))


def _get_json(url: str, params: dict):
    """GET → エラー処理 → JSON。nasa_get / public_get の共通部分。"""
    try:
        resp = httpx.get(url, params=params, timeout=30)
    except httpx.HTTPError as e:
        sys.exit(f"通信エラー: {e}")

    remaining = resp.headers.get("X-RateLimit-Remaining", "不明")
    print(f"X-RateLimit-Remaining: {remaining}", file=sys.stderr)

    if resp.status_code == 429:
        sys.exit(
            f"レート制限に達しました (429)。残り: {remaining}。"
            "時間をおくか、自分の API キーを使ってください。"
        )
    if resp.is_error:
        sys.exit(f"HTTPエラー {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def unescape(v):
    """WordPress 由来の &amp; などの HTML エンティティを戻す。文字列以外はそのまま返す。"""
    return html.unescape(v) if isinstance(v, str) else v
