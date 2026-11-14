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
- `fetch_amedas.py`: 気象庁アメダス 7 地点の日別値（最大瞬間風速など）を `data/` に保存する
- `fetch_maff_damage.py`: 農水省の作物統計から、茨城・千葉の水稲の風水害被害（年別）を集める
- `fetch_disaster_damage.py`: 農水省「農作物災害種類別被害統計」から、災害ごとの茨城・千葉の水稲被害を集める（被害なしの災害も分かる）。`--all-prefs` で全都道府県、`--offline` でキャッシュだけから作り直す
- `fetch_imerg.py`: NASA GPM IMERG（日別 0.1°）を OPeNDAP で範囲だけ切り出す（Earthdata のトークンが必要）
- `phenology.py`: NASA POWER の気温から、品種ごとの出穂日・出穂後積算気温・倒れやすい田の割合を推定する
- `analyze_disasters.py`: 災害統計を正解にして、嵐ごとに雨・風・生育段階との関係を検定する
- `fetch_geos_forecast.py`: NASA GEOS-FP の予報（1 時間ごとの雨・10 m 風速）を範囲で取得する
- `analyze_early_harvest.py`: 過去の台風で、NASA のデータの規則なら、しなくてよい早刈りを何回減らせたかを数える
- `analyze_enso.py`: エルニーニョ・ラニーニャ（ONI）と、倒伏の条件に当たった台風の年ごとの数の関係を検定する
- `lodging_model.py`: 軽量な倒伏予測モデル（雨 × 実り具合の規則と、表示用のロジスティック回帰。品種別）
- `predict_lodging.py`: NASA のデータを取りに行き「刈る／待ってよい」を出す（`--replay 日付` で過去の台風を再現）
- `review_lodging_model.py`: 茨城・千葉モデルのレビュー（基準・期間を変えた頑健性、並べ替え検定、未知の台風）
- `analyze_japan.py`: 全国の都道府県×台風で、解析（被害あり／なしの比較）とモデルの比較（台風を 1 つずつ抜く交差検証）をする
- `analyze_japan_location.py`: 全国モデルに場所の変数（緯度経度・地方・都道府県）を入れる価値を、見分ける力（AUC）と確率の当たり方（Brier・地方ごとの偏り）に分けて比べる
- `analyze_episodes.py`: 嵐ごとに、倒伏の報告がある嵐の位置と検定を出す
- `build_japan_dataset.py`: 全国版の学習用データ「都道府県 × 台風」（2004〜2021 年 8〜9 月、500 km 以内）を作る。水稲被害面積と IMERG の雨・POWER の気温と風を付けて `data/japan_typhoon_dataset.csv` に保存
- `results/`: 解析結果の図とレポート
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
