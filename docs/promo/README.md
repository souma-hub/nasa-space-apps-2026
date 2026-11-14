# 30 秒プロモーション動画（英語）— 作業指示書

NASA Space Apps 提出用。クラウド（リモート）セッションで作る前提の引き継ぎメモ。

## 締切と前提
- 提出締切: 2026-11-15 14:00 JST（東京会場）。動画は遅くとも 12:00 までに仕上げる
- 提出要件（長さ・形式・提出先）は本体セッションで公式を確認中。確定したらこの節に追記する。分かるまでは「30 秒以内、英語、MP4（1920×1080, H.264 + AAC）」で作る
- NASA のロゴ・NASA の公式画像は使わない（自前の写真・画面・文字だけで作る）

## 原稿（英語、約 75 語）— **オーナー承認待ち。承認前に音声を確定しない**
```
When a typhoon is forecast, many rice farmers in Japan harvest early,
even before the grain is fully ripe, because there is no clear rule
for when it is safe to wait.
Windfall Rice builds that rule from NASA data:
GPM IMERG rainfall and NASA POWER wind and temperature.
Tested on 23 past typhoons, it said "safe to wait" in 10 of 16 no-damage cases,
missing 1 of 7 damaging ones.
It runs on a laptop, or even a Raspberry Pi Pico.
NASA data for harvest decision support.
```
- 誇張しない（「未熟＝青い稲」のような表現はしない。「fully ripe」まで）
- 数字はスライドと同じ: 10 / 16、1 / 7、23 台風（`docs/priorities.md` が正）

## 絵コンテ（目安 6 カット × 約 5 秒）
| # | 秒 | 画 | 文字（英語、画面下か中央） |
|---|---|---|---|
| 1 | 0–5 | `assets/field.jpg`（ゆっくりズーム） | Typhoon forecast. Harvest now, or wait? |
| 2 | 5–10 | 同じ写真を暗くして文字 | No clear rule → early harvest of not-yet-ripe rice |
| 3 | 10–15 | 文字カード（入力 3 つを並べる） | NASA GPM IMERG rain · NASA POWER wind & temperature |
| 4 | 15–21 | 大きな数字 | 10 / 16 safe to wait · 1 / 7 missed (23 past typhoons) |
| 5 | 21–26 | `assets/demo.png`（＋あれば Pico の LED 実写） | Runs on a laptop or a Raspberry Pi Pico |
| 6 | 26–30 | `assets/frog.jpg` | NASA data for harvest decision support — Windfall Rice |

- 文字カードの配色はスライドに合わせる: 背景 #fbfaf6、文字 #1d1b19、強調 #b3261e、セリフ体見出し
- 字幕（英語）は焼き込む。無音でも内容が分かるようにする

## 作り方（案）
- 文字カード: Pillow で 1920×1080 の PNG を生成（フォントは Noto Serif / Noto Sans）
- 音声: 英語 TTS。品質順に検討（使えるものを使う）: Piper（オフライン、en_US の声） > espeak-ng（最終手段）。音声の長さに合わせて各カットの秒数を調整し、合計 30 秒以内
- 合成: ffmpeg（`-loop 1` の静止画 + `zoompan` で軽い動き、`xfade` でつなぐ、音声を合わせて `-shortest`）
- スクリプトは `make_promo.py` としてリポジトリ直下に置き、出力は `out/promo.mp4`（out/ は gitignore 済み）。完成版だけ `docs/promo/promo.mp4` にコピーしてコミット（サイズが大きすぎなければ）

## 素材
- `assets/field.jpg`: 田んぼの写真（オーナー撮影、EXIF 除去済み）
- `assets/frog.jpg`: 稲とカエルの写真（同上）
- `assets/demo.png`: デモ画面（docs/demo/index.html、1366×768）。必要なら headless ブラウザで撮り直してよい
- Pico の LED 実写: 未撮影。オーナーが撮れたら追加

## 確認
- 長さ 30 秒以内（`ffprobe` で確認）、音声と字幕のずれがない、数字がスライドと一致
- 完成したら本体（オーナー）に見せて承認をもらう。提出はオーナーが行う
