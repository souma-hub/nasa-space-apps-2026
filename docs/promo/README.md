# 30 秒プロモーション動画（英語）— 作業指示書

NASA Space Apps 提出用。クラウド（リモート）セッションで作る前提の引き継ぎメモ。

## 締切と前提
- 東京会場の締切: 2026-11-15 14:00 JST（オーナー情報）。動画は遅くとも 12:00 までに仕上げる。公式のグローバル締切は 11/15 23:59（ローカル時刻）
- 公式要件（Project Submission Guide、2026-11-15 にブラウザで確認）:
  - デモは **30 秒以下の動画** か **7 枚以内の英語スライド**。超えると Global Judging の対象外。**29 秒台で作る**
  - 動画は英語（他言語の場合は英語字幕必須）。NASA サイトには上げられないので、YouTube・GitHub 等に置き、**ログイン不要の公開リンク**を提出
  - 推奨の流れ: 0:00 名前とチーム名 → 0:02 お題 → 0:05 プロジェクト名と一言 → 0:10 仕組みと NASA データ → 0:20〜0:30 未来
  - **SI（AI）生成物の表示が必須**: 生成した画像・動画には見える透かし、**生成音声（TTS）は説明文とメタデータで明記**。→ 動画の最後に小さく「Voice: AI-generated (TTS)」を入れ、MP4 の metadata（comment）にも書く
  - NASA のロゴ・旗・ミッション標章など NASA のブランド要素は使わない。18 歳未満の人物の画像・声は入れない
  - 使った素材・ツールはすべて提出ページに列挙する（写真はオーナー撮影）
- 出力: MP4（1920×1080, H.264 + AAC）

## 原稿（英語、約 80 語）— **オーナー承認待ち。承認前に音声を確定しない**
```
We're Windfall Rice, tackling the Field Shift challenge.
When a typhoon is forecast, many rice farmers in Japan harvest early,
even before the grain is fully ripe, because there's no clear rule
for when it's safe to wait.
We built that rule from NASA data:
GPM IMERG rainfall and NASA POWER wind and temperature.
Tested on 23 past typhoons, it said "safe to wait" in 10 of 16 no-damage cases,
missing 1 of 7.
It even runs on a Raspberry Pi Pico.
Next: comparing planting choices, for any region and crop.
```
- 試作版（`make_promo.py`）の最終行: "It shows when current crops are most vulnerable, and compares planting strategies."（お題の文言に寄せた差し替え。未承認）。読み上げが長いため「GPM IMERG rainfall and NASA POWER wind and temperature」は読み上げから外し、画面の文字のみ
- メンバーの名前を入れるかはオーナーが決める（入れるなら冒頭）
- 30 秒に収まらなければ、「GPM IMERG rainfall and NASA POWER wind and temperature」を画面の文字だけにして読み上げから外す
- 誇張しない（「未熟＝青い稲」のような表現はしない。「fully ripe」まで）
- 数字はスライドと同じ: 10 / 16、1 / 7、23 台風（`docs/priorities.md` が正）

## 絵コンテ（目安 6 カット × 約 5 秒）
| # | 秒 | 画 | 文字（英語、画面下か中央） |
|---|---|---|---|
| 1 | 0–4 | `assets/field.jpg`（ゆっくりズーム） | Windfall Rice · Field Shift challenge |
| 2 | 4–10 | 同じ写真を暗くして文字 | Typhoon forecast → harvest now, or wait? No clear rule. |
| 3 | 10–15 | 文字カード（入力を並べる） | NASA GPM IMERG rain · NASA POWER wind & temperature |
| 4 | 15–21 | 大きな数字 | 10 / 16 safe to wait · 1 / 7 missed (23 past typhoons) |
| 5 | 21–25 | `assets/demo.png` → `assets/pico_led.mp4`（LED 実写） | Runs on a laptop or a Raspberry Pi Pico |
| 6 | 25–29.5 | `assets/frog.jpg` | NASA data for harvest decision support · Voice: AI-generated (TTS) |

- 文字カードの配色はスライドに合わせる: 背景 #fbfaf6、文字 #1d1b19、強調 #b3261e、セリフ体見出し
- 字幕（英語）は焼き込む。無音でも内容が分かるようにする

## 作り方（案）
- 試作版は Windows の SAPI（Microsoft Zira、英語）で音声を生成し、`python make_promo.py` で `out/promo_draft.mp4` を作る（話速は 29.5 秒以内に収まるよう自動調整、ネットからのダウンロードなし）。Pillow でフレームを描画して ffmpeg に渡す方式。MP4 の comment に "Narration: AI-generated text-to-speech (Windows SAPI)" を入れてある。以下の Piper 案は未使用
- 文字カード: Pillow で 1920×1080 の PNG を生成（フォントは Noto Serif / Noto Sans）
- 音声: 英語 TTS。品質順に検討（使えるものを使う）: Piper（オフライン、en_US の声） > espeak-ng（最終手段）。音声の長さに合わせて各カットの秒数を調整し、合計 30 秒以内
- 合成: ffmpeg（`-loop 1` の静止画 + `zoompan` で軽い動き、`xfade` でつなぐ、音声を合わせて `-shortest`）
- スクリプトは `make_promo.py` としてリポジトリ直下に置き、出力は `out/promo.mp4`（out/ は gitignore 済み）。完成版だけ `docs/promo/promo.mp4` にコピーしてコミット（サイズが大きすぎなければ）

## 素材
- `assets/field.jpg`: 田んぼの写真（オーナー撮影、EXIF 除去済み）
- `assets/frog.jpg`: 稲とカエルの写真（同上）
- `assets/demo.png`: デモ画面（docs/demo/index.html、1366×768）。必要なら headless ブラウザで撮り直してよい
- `assets/pico_led.mp4`: Pico H の LED 実写（オーナー撮影の切り抜き 8.3 秒、30fps、Pico 周辺を 2 倍に拡大、音声と位置情報などのメタデータは除去済み）。2 秒ごとに 点灯→点灯→消灯→… と変わる。5 カット目で点灯→消灯が 1 回映る 4 秒を使う

## 確認
- 長さ 30 秒以内（`ffprobe` で確認）、音声と字幕のずれがない、数字がスライドと一致
- 完成したら本体（オーナー）に見せて承認をもらう。提出はオーナーが行う
