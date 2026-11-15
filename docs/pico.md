# Raspberry Pi Pico H で判断を動かす（低スペック動作の検証）

統一モデルの判断を、数百円のマイコン（Raspberry Pi Pico H、RAM 264 KB、クロック 133 MHz）の上で動かす。
プログラムは `deliverable/pico/main.py`（約 6 KB、`make_pico.py` が `results/unified_model.json` から自動で作る）。PC 版（`demo_lodging.py`）と同じ判断・確率になることを確認済み。

## 用意するもの
- Raspberry Pi Pico H
- **データ通信ができる** micro-USB ケーブル（充電専用だと認識しない。確かめ方は手順 1）
- PC に Thonny（無料。https://thonny.org/ ）

## 手順
1. **ケーブルの確認と MicroPython の書き込み**
   - Pico の白いボタン（BOOTSEL）を押したまま USB を PC に挿し、挿したらボタンを離す
   - PC に「RPI-RP2」というドライブが出れば、ケーブルはデータ通信に対応している。何も出なければ充電専用なので、別のケーブルにする
   - Thonny を開き、右下のインタプリタ表示（または「ツール」→「オプション」→「インタプリタ」）で「MicroPython (Raspberry Pi Pico)」を選び、「MicroPython をインストール」で書き込む
     - 手で書く場合: https://micropython.org/download/RPI_PICO/ の .uf2 を RPI-RP2 ドライブにドラッグする（Pico 2 なら RPI_PICO2）
2. **プログラムを入れる**
   - Thonny で `deliverable/pico/main.py` を開く
   - 「ファイル」→「名前を付けて保存」→「Raspberry Pi Pico」→ 名前を `main.py` にして保存
3. **実行する**
   - Thonny の緑の実行ボタン（F5）。下のシェルに結果が出る
   - 基板の LED: **点灯＝刈る、消灯＝待ってよい**（シナリオごとに 2 秒）
   - `main.py` という名前で保存したので、PC から外してモバイルバッテリーにつないでも、電源を入れるだけで LED のデモが動く

## 期待する表示（一部）
```
倒伏（台風）の刈り取り判断 - 統一モデル on Raspberry Pi Pico
空きメモリ ... バイト（Pico の RAM は 264 KB）
■ 強い台風が直撃、稲は実っている (茨城)
  判断: 【刈る】 確率 88%（閾値 17%、計算 ... マイクロ秒）
■ 中くらいの台風、ただし稲がまだ実りきっていない (茨城)
  判断: 【待ってよい】 確率 16%（閾値 17%、計算 ... マイクロ秒）
```
「計算 ... マイクロ秒」と「空きメモリ」が、低スペックで動く根拠の数字になる（実機で測って発表に使う）。

## 発表での言い方（素材）
- 「判断の計算は、数百円のマイコンでも動きます。必要なのは、雨・風・気温の数字が 1 日に数個だけです」
- 展望: 重い衛星データの処理は NASA 側で済ませ、数十バイトの数字だけを、低速な通信（衛星通信やショートメッセージ）で届ければ、インターネットのない地域でも判断できる。ただし、その地域の被害の記録で学習し直す必要がある

## うまくいかないとき
- RPI-RP2 が出ない → ケーブルを替える。BOOTSEL を押したまま挿しているか確認する
- Thonny が Pico を見つけない → 右下のインタプリタを「MicroPython (Raspberry Pi Pico)」にし、ポートを選び直す。USB を挿し直す
- 日本語が化ける → Thonny のシェルは UTF-8 で表示できるので、通常は化けない。化けたら英語表示に切り替えるので知らせる

## 実機での確認（2026-11-14）
- 機材: Raspberry Pi Pico H（RP2040）、MicroPython v1.29.0（`RPI_PICO-20260824-v1.29.0.uf2`）
- 書き込みと実行は Thonny の代わりに `mpremote` でもできる（インストール不要: `uvx mpremote connect COM3 run deliverable/pico/main.py`、保存は `uvx mpremote connect COM3 cp deliverable/pico/main.py :main.py`。COM 番号は PC ごとに違う）
- 結果: 10 シナリオすべてで、判断と確率（% 表示）が PC 版 `demo_lodging.py` と一致
- 計算時間: 1 回 0.6〜1.2 ms。空きメモリ 221,808 バイト（RAM 264 KB のうち）
- `main.py` として Pico に保存済み。USB 電源をつなぐだけで LED のデモが動く

## 閾値の安全マージン（2026-11-15）
- 房総半島台風（2019 年 15 号）の確率が茨城・千葉の閾値（被害ありの最小確率）と同値で、単精度の Pico では `p >= thr` が不定だった。保存する閾値を 0.999 倍にした（全国 0.0894、茨城・千葉 0.1674）。PC・JS・Pico は同じ保存値を使う
- 実機（COM3、MicroPython）で過去 23 台風を流し、PC 版と判断 23/23 一致。2019 年 15 号は両方「刈る」（Pico の確率 0.16756908、閾値 0.16740145）

## 発表当日の手順（単体デモ版 `deliverable/pico/demo_main.py`）
開発環境のないノート PC でも動かせる。Pico には `deliverable/pico/demo_main.py` を `main.py` として保存済み（`make_pico.py` が `results/unified_model.json` から自動で作る。以前の `main.py` は `deliverable/pico/backup_main.py` に退避）。

1. **ノート PC に USB で挿すだけ**。BOOTSEL ボタンを**押しながら挿さない**（書き込みモードになり、プログラムが動かない。挿し直せば戻る）
2. 起動すると LED が 1 秒点灯して消える（起動の合図）
3. **BOOTSEL ボタンを押すたび**に、次のシナリオを交互に判断する。押すと LED が短く 3 回点滅（計算した合図）してから結果が出る
   - 1 回目: 「強い台風が直撃、稲は実っている」（茨城）→ **点灯したまま＝刈る**
   - 2 回目: 「台風が遠くを通る」（千葉）→ **消灯＝待ってよい**
4. **画面に出す場合**: ノート PC の Edge（または Chrome）で `deliverable/demo/serial.html` を開く（ファイルをダブルクリックでよい）→「Pico に接続」→ 一覧から Pico（USB シリアルデバイス）を選ぶ。ドライバのインストールは不要（Windows 10 以降）。入力を変えて「Pico で判断」を押すと、Pico 上で計算した判断・確率・閾値・計算時間（マイクロ秒）が大きく出る。基板のボタンを押したときの判断も、同じ画面の別の欄に出る
   - 同時に他のソフト（Thonny、`mpremote`）が COM ポートを使っていると接続できない。先に閉じる
   - `mpremote` などで REPL に入ると `main.py` が止まる。Pico の USB を挿し直せば再開する
5. **うまくいかないときの予備**: LED の動画 `docs/promo/assets/pico_led.mp4`
6. モバイルバッテリーにつないでも動く（LED のデモだけ。画面表示には PC が要る）

### 画面の使い分け（`deliverable/demo/pico.html`）
- 画面が使えるとき: Edge / Chrome で `deliverable/demo/pico.html` を開き、「Pico に接続」を 1 回押す。上部のタブで 2 つの画面を切り替える（Pico は `demo_main.py` のまま）
  - 「入力を送って判断」: 入力欄から命令を送り、Pico の判断（刈る／待ってよい、確率、閾値）を出す。シリアルの応答だけ表示
  - 「Pico 単体の判断」: 基板の BOOTSEL ボタンを押したときの結果を受けて出すだけ。ボタン由来の応答だけ表示
- 画面が使えないとき: ボタンと LED だけで実演する
- Web Serial は同時に 1 ページしかポートを開けないので、2 つの画面は 1 ファイルの中にまとめてある

### シリアルの仕様
- 送る: 1 行 `県,過去雨,予報雨,風,gdd[,品種]`（例 `茨城,40,80,18,900`。品種は `koshihikari` など、省略するとコシヒカリ）
- 返る: 1 行の JSON `{"src": "serial"|"button", "harvest": true, "decision": "刈る", "prob": 0.8798, "threshold": 0.1674, "us": 842, "pref": "茨城"}`。入力が不正なら `{"error": "..."}`
- ボタンの処理（`on_button`）もシリアルの処理（`on_line`）も、同じ `judge()` から同じ `decide()` を呼ぶ

### 実機での確認（2026-11-15）
- 書き込みは `uvx mpremote connect COM3 cp deliverable/pico/demo_main.py :main.py`
- シリアル往復で、23 台風（`results/unified_kanto_loo.csv`、茨城・予報 0）の判断が PC 版 `lodging_unified.decide` と 23/23 一致。計算は約 0.8〜0.9 ms
- ボタンは物理的に押せないため未確認（ボタンのロジックはシリアルと同じ `decide` を使うことをコードで担保）。`serial.html` も実ブラウザでは未確認（JS の構文チェックのみ）
