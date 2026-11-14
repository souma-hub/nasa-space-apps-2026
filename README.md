# nasa-api — NASA ハッカソンに向けた API 練習

2026-10-28 に Playground/nasa-api として作成し、2026-11-09 にこのフォルダへ移した。NASA Space Apps Challenge 2026（2026-11-14〜15）に向けた練習と本番用のリポジトリ。外出先から作業する方法は [REMOTE.md](REMOTE.md) を参照。

## 目的
ハッカソン本番の前に、NASA の公開 API の使い方（認証・レート制限・データの形）に慣れておく。

## 練習の候補（使う前に、今も提供されているかを確認すること。状況は 2026-11-09 時点）
| 名前 | 中身 | 認証 | 練習としての価値 | 状況 |
|---|---|---|---|---|
| APOD | 毎日の天文写真と解説 | 新: 不要 / 旧: API キー | 最初の1本。GET と JSON の基本 | 旧 API（api.nasa.gov/planetary/apod）は HTTP 500。新エンドポイント `science.nasa.gov/wp-json/wp/v2/apod-basic`（2026-11-09 に動作を確認した）に切替済み。2026-12-01 に旧側（nasa/apod-api）はアーカイブ予定 |
| NeoWs（api.nasa.gov） | 地球に近づく小惑星 | API キー | 日付で範囲を指定する、ページ送り、集計 | 稼働確認 |
| DONKI（api.nasa.gov） | 太陽フレアなどの宇宙天気 | API キー | イベントのデータを時系列で扱う | 503 で未確認。CCMC 側 `https://ccmc.gsfc.nasa.gov/DONKI-API/get/` に移った可能性（未確認） |
| EONET v3 | 山火事・火山などの自然現象（位置付き） | 不要 | 地図に表示する練習（GeoJSON） | 稼働確認 |
| NASA Image and Video Library（images-api.nasa.gov） | 画像・動画の検索 | 不要 | 検索とメディアの扱い | 稼働確認 |
| GIBS | 衛星画像のタイル | 不要 | 地図アプリに衛星画像を重ねる | Suomi NPP が 2026-11-02 に新規観測を停止し、NOAA-20/21 へ移行 |
| Earthdata（CMR など） | 地球観測データの本体 | Earthdata Login が必要 | ハッカソンの課題で使われがち。大きいデータの扱い | 未確認 |
| Mars Rover Photos | 火星探査車の写真 | API キー | （表から外している） | 404。旧実装は 2025-10 にアーカイブ |

- API キーは https://api.nasa.gov で無料で発行できる。`DEMO_KEY` はレート制限が厳しいので、練習を始めたら自分のキーを取る
- レート制限: `DEMO_KEY` は 30回/時・50回/日（IP 単位）、個人キーは 1,000回/時
- キーはコードに直接書かず、環境変数か `.env` に置いて `.gitignore` に入れる（公開リポジトリに漏らさない）

## 作成済みスクリプト
`uv run` で実行する（依存は各ファイル先頭の PEP 723 ヘッダで解決される）。

注意: Windows の文字化け対策として、出力は nasa_common.py で UTF-8 に固定している。2026-11-09 に apod.py（新エンドポイント）と neows.py の動作を確認した。

```
uv run apod.py                      # 今日の APOD（新エンドポイント、キー不要）
uv run apod.py --date 2024-01-01    # 日付指定（新側では apod-basic/240101 になる）
uv run apod.py --json               # 生 JSON（形状の確認用）
uv run apod.py --legacy             # 旧 API（キー付き。現在は 500 の見込み）
uv run neows.py                     # 今日から7日間の接近小惑星 上位10件
uv run neows.py --start 2026-11-09 --days 3
```

API キーの置き方（`apod.py --legacy` と `neows.py` が使う。未設定なら `DEMO_KEY` で警告つき実行）:
1. このフォルダに `.env` を作り、`NASA_API_KEY=取得したキー` と1行書く
2. `.gitignore` に `.env` を入れる
3. 環境変数 `NASA_API_KEY` が設定済みならそちらが優先される

## 練習の段階（案）
1. APOD を1回呼んで、タイトルと画像の URL を表示する（API キーと JSON の基本）
2. NeoWs で1週間分の小惑星を取り、一番近づくものを表にする（パラメータとページ送り）
3. EONET の現象を地図に表示する（位置データと可視化）
4. 2つ以上の API を組み合わせた小さなアプリ（ハッカソンの予行演習）

## 未確認のこと
- DONKI の移行先（CCMC 側に移ったかは未確認）
- 上の各 API が今も提供されているか（終了・移行したものがありうる。状況欄は 2026-11-09 時点）
- NASA Space Apps Challenge 2026 は 2026-11-14〜15 とのこと（第三者情報、公式サイトは未確認）。日程・課題・チームの条件も要確認

## 発表用デモ画面
統一モデルの「刈る／待ってよい」判断を、ブラウザで動かして見せる 1 ファイル完結の画面（外部通信なし、オフラインで動く）。
- 作る: `uv run make_demo.py`（`results/unified_model.json`・`results/unified_kanto_loo.csv`を埋め込んで `docs/demo/index.html` を生成）
- 開く: `docs/demo/index.html` をブラウザで開く（プロジェクター向け 16:9。入力を動かすと即時に再計算）
- 検証: `uv run check_demo.py`（JS の判定が Python の `decide()` と一致するかを node で確認）
- 入力の初期値は URL クエリで渡せる: `index.html?pref=茨城&variety=koshihikari&past=40&forecast=80&wind=18&gdd=900`（どれも省略可。不正値は既定値）。シナリオはこの URL を手元に持つ運用
  - 強い台風が直撃、稲は実っている: `?pref=茨城&past=40&forecast=80&wind=18&gdd=900`
  - 同じ台風、ただし稲がまだ青い: `?pref=茨城&past=40&forecast=80&wind=18&gdd=250`
  - 九州に強い台風（全国の部分だけ）: `?pref=鹿児島&past=60&forecast=100&wind=20`
