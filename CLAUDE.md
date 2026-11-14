# nasa-space-apps-2026

NASA Space Apps Challenge 2026（2026-11-14〜15）の練習と本番用のリポジトリ。GitHub の非公開リポジトリ souma-hub/nasa-space-apps-2026 として管理する。

## 構成
- `README.md`: 練習する API の一覧と状況（提供状況は 2026-11-09 時点）、スクリプトの使い方
- `REMOTE.md`: 外出先から Claude Code を使うためのガイド（中学生向け）
- `PLAN.md`: 本番のタイムテーブル、Claude の利用リソース、進め方（SDD・仮）
- `TEAM.md`: チーム登録用のディスクリプション（日本語版と英語版）
- `lodging_s1.py`: Sentinel-1 で水田の倒伏前後の変化を、前年同期と比べる
- `fetch_fude.py`: 筆ポリゴン（田）を範囲指定で取得し `data/` に保存する
- `lodging_parcel.py`: 筆ポリゴンの区画ごとに Sentinel-1 を平均して変化を比べる
- `events.csv`: 倒伏イベントの一覧（期間・地域・確度・出典）。ネットの情報から手で追記する
- `build_dataset.py`: NASA POWER の時間値と events.csv から学習用データ（`data/dataset.csv`, `data/sequences.npz`）を作る
- `analyze_threshold.py`: 倒伏あり／報告なしの日で気象を検定し、閾値の材料を出す
- `results/`: 解析結果の図
- `data/`: 取得したデータ（コミットしない）
- `apod.py`: APOD（毎日の天文写真）を取得して表示する
- `neows.py`: NeoWs（地球に近づく小惑星）を取得して表にする
- `nasa_common.py`: API キーの読み込みや出力の UTF-8 固定など、共通処理
- `.env.example`: `.env` の書き方の見本（本物の `.env` はコミットしない）

## ルール
- API キーは `.env` か環境変数 `NASA_API_KEY` に置く。絶対にコミットしない
- スクリプトは `uv run xxx.py` で実行する（PEP 723 のヘッダで依存を解決する）
- 新しい API を使う前に、提供状況を確認する（README の状況欄を参照）
- 出力の文字化け対策は nasa_common.py の reconfigure に依存している。新しいスクリプトでも使うこと
- クラウドセッションでは `~/.claude/settings.json` の deny ルールが効かない。外部への送信には特に注意する
- 回答・出力は日本語で行う

## push の方針
- 非公開リポジトリなので、コミットしたらすぐ push する（特にドキュメント）。デスクトップ PC が落ちても、クラウドセッションで続きをやれるようにするため
- コミットの author / committer のメールアドレスが `294825900+souma-hub@users.noreply.github.com` であることを確認する
