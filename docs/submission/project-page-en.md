# Windfall Rice: Submission Page Draft (English)

Draft for the NASA Space Apps Challenge 2026 project page. Sections follow the order of the official form. Items marked `[TBD: ...]` are filled in by the team at submission time. The Japanese memo at the end is for the team only and must be removed before submitting.

---

## 1. Project Name

**Recommended: Harvest Now or Wait? — NASA data for typhoon harvest decisions**

Other candidates:
- Windfall Rice: A "Safe to Wait" Signal for Typhoon Season
- Wait or Harvest: Rice Decisions Under Typhoon Forecasts

Team name: **Windfall Rice**
Challenge: **Field Shift**

---

## 2. High-Level Project Summary

When a typhoon is forecast, many rice farmers in Japan harvest early, sometimes before the grain is fully ripe, because they have no clear rule for when it is safe to wait. We built a small model that uses NASA GPM IMERG rainfall, NASA POWER wind and temperature, and GEOS-FP forecasts to give a simple signal: "harvest now" or "safe to wait". Tested on 23 past typhoons in Ibaraki and Chiba, leaving one typhoon out at a time, it said "safe to wait" in 10 of the 16 typhoons that caused no major damage, and missed 1 of the 7 that did. It runs on a laptop or on a Raspberry Pi Pico microcontroller. We also made a rough comparison of planting choices, a first step toward Field Shift's goal of exploring crop options. It is decision support, not a replacement for farmer judgment. The method itself is reusable: any region or crop with NASA data and a record of past damage can build its own rule the same way.

---

## 3. Link to Project Demo / Link to Final Project

- Project demo (7-slide deck, PDF): https://github.com/souma-hub/nasa-space-apps-2026/blob/main/deliverable/slides/windfall-rice-slides.pdf
- Final project (public repository): https://github.com/souma-hub/nasa-space-apps-2026

---

## 4. Detailed Project Description

### What it does

Typhoon forecasts say "heavy rain and strong wind". They do not say whether a particular rice crop will be damaged, or whether it is safe to wait. A farmer we know told us that when a forecast comes, they harvest early to be safe, even if the rice is not yet ready. This matches public guidance from the Chiba and Ibaraki prefectural governments: the best harvest time is about 35 to 40 days after heading, and harvesting earlier raises the share of immature grain and lowers the inspection grade.

Windfall Rice takes the forecast rain, the recent rain, wind, and how far the crop has ripened, and returns one of two answers: **harvest now** or **safe to wait**. The goal is to reduce early harvests that were not needed. The farmer decides. We provide a basis for that decision.

### How it works

**Inputs (all from NASA):**
- Rain that has already fallen: GPM IMERG (daily, 0.1 degree).
- Wind and air temperature: NASA POWER. Temperature is used to estimate how far the crop has ripened (accumulated temperature after heading).
- Forecast rain and wind for the next two days: GEOS-FP.

**Model.** One logistic regression with a few coefficients, trained on 1,815 prefecture-typhoon records from 86 typhoons across Japan. The national part uses rain, wind, and a per-prefecture correction. For Ibaraki and Chiba, where we have local knowledge of varieties and planting times, we add a local term for the stage when rice is most exposed (roughly 400 to 1,500 degrees C of accumulated temperature after heading). Rice that is still immature is much less likely to lodge, which matches what the farmer told us. The decision threshold is set low (about 17% for Ibaraki and Chiba) on purpose, because missing a damaging typhoon costs more than a cautious call.

### Validation

We checked the model against 23 typhoons that came within 300 km of southern Kanto in August and September, 2004 to 2021. The reference answer is the Ministry of Agriculture, Forestry and Fisheries (MAFF) disaster statistics: 7 typhoons caused paddy damage of 100 ha or more in Ibaraki and Chiba, and 16 did not. We left out one typhoon at a time, including from the national training data, and predicted it.

- Today's practice, harvesting at every typhoon warning, would mean harvesting early 23 times, 16 of them for typhoons that caused no major damage.
- Our model said "safe to wait" in **10 of those 16**, and missed **1 of the 7** damaging typhoons: the 2019 Boso Peninsula typhoon (Typhoon Faxai). It was a small, strong typhoon, and the grid-based NASA wind was weak (6.9 m/s), so the model did not flag it. We report this openly.
- Across Japan, leaving one typhoon out at a time, adding wind to rain raised the AUC from 0.82 to 0.88.

### Planting strategy comparison (rough estimate)

Field Shift suggests tools may highlight "seasons when current crops appear more vulnerable" and compare "at least three rotation strategies, including the existing rotation". We did not build a crop rotation tool. As a first, simple step, we took the vulnerable stage above and asked how often typhoons overlapped it in a 45-year record (1981 to 2025, typhoons passing within 300 km of one point in Ibaraki, July to October, 113 typhoons), using NASA POWER temperature to estimate heading dates:

| Strategy (all rice) | Typhoons overlapping the vulnerable stage |
|---|---|
| Existing practice (Koshihikari) | 54 of 113 |
| Plant 3 weeks later (Koshihikari) | 56 of 113 |
| Early variety (Akitakomachi) | 38 of 113 |
| Late variety (Nijinokirameki) | 57 of 113 |

Only the early variety reduced the overlap. Treat this as an estimate only: heading is estimated from temperature alone (day-length response is ignored, so later planting is probably shown as more delayed than it would be), it uses one location, it counts overlaps and not actual damage, and it does not compare yield, quality, or workload. These are variety and planting-date options within rice, not a full crop rotation.

### Runs anywhere

The decision needs a few numbers and a few coefficients. On a PC one decision takes a few microseconds. On a Raspberry Pi Pico H (RP2040, 264 KB RAM, a board that costs about US$5) running MicroPython, one decision takes about 0.6 to 1.2 ms. On the Pico, the 23 past typhoons gave the same decisions as the PC (23 of 23), and the demo scenarios matched in both decision and displayed percentage. There is no cloud service and no vendor lock-in. The coefficients are plain numbers that anyone can copy. There is also a single-file browser demo that works offline.

### Benefits

- Gives farmers a data-based reason to wait when waiting is likely safe, so they can harvest closer to the best time and avoid immature grain.
- Uses only free, global NASA data and a light model, so it does not require special equipment.
- Honest about what it cannot do (see below).

### Limitations

- The reference is at prefecture level (Ibaraki plus Chiba), not individual fields. Field-level records do not exist yet.
- Only 23 typhoons in the validation set. One typhoon changes the picture.
- NASA's grid wind (about 50 km) can miss gusts from small, strong typhoons. We missed the 2019 Boso Peninsula typhoon for this reason.
- The reference is total wind and flood damage to paddy rice, not lodging alone.
- We have not evaluated the effect of forecast errors. The model was trained on observed rain and wind, and used with forecasts.
- The threshold was tuned on past data. The "10 of 16" figure is a past result, not a promise for future typhoons.
- Soil health, water use, and the crop combination in a rotation are not handled.

### What we tried that did not work

We first tried to see lodged fields directly from space. Sentinel-1 radar (ESA) change showed essentially no link with lodging (correlation about 0.05), and averaging over individual field polygons did not help. NASA POWER wind also did not reproduce typhoon gusts in the Kanto case. We also tested whether El Nino and La Nina years could guide planting choices; we found no relationship with the number of damaging typhoons (1981 to 2026). We kept these negative results because they shaped what we built.

### What we hope to achieve

The method is the same wherever there are NASA data and a record of past damage: take an official damage record, test NASA-derived variables, choose them by leaving one event out, and keep a light model. We hope to apply it to other regions, crops (wheat, soybean, fruit), and hazards. We have not tested this yet. If farmers and cooperatives record predictions and outcomes (harvested or waited, damage or none), that history could become material for planning planting dates, varieties, and eventually crop rotation. This is our direction, not something we have built.

### Tools

Python with uv; httpx, NumPy, pandas, SciPy, scikit-learn, xarray, netCDF4 for data and analysis; MicroPython (Thonny and mpremote) on a Raspberry Pi Pico H; a single-file HTML demo and slides; ffmpeg and Windows SAPI text-to-speech (an English system voice, Microsoft Zira preferred; AI-generated) for the demo video.

---

## 5. Use of Super Intelligence (SI)

We used Anthropic's Claude (through Claude Code) widely: to write code, process data, run analyses, and draft documents and slides. The idea came from the team, based on a farmer friend's experience of harvesting early before typhoons. The team set the direction and made the decisions on what to adopt or drop, and reviewed and checked the results. The voice in our demo video is generated by text-to-speech (AI-generated). We did not generate any images; the photographs are taken by the team.

---

## 6. NASA Data

| Data | Role |
|---|---|
| GPM IMERG Daily, Final Run, V07 (GPM_3IMERGDF). Near-real-time Late Run (GPM_3IMERGDL) for the latest days. https://gpm.nasa.gov/data/imerg and the NASA Earthdata CMR https://cmr.earthdata.nasa.gov | Rain that has already fallen (past 2 days before the decision); main training input. |
| NASA POWER, daily point API (community AG). Variables: T2M (air temperature at 2 m) and WS10M_MAX (daily maximum wind at 10 m). https://power.larc.nasa.gov/api/temporal/daily/point | Temperature gives accumulated temperature after heading (how ripe the crop is). Wind is an input to the national model. |
| GEOS-FP forecasts (NASA GMAO, 0.25 degree). https://opendap.nccs.nasa.gov/dods/GEOS-5/fp/0.25_deg/fcast | Forecast rain and 10 m wind for the next 48 hours at decision time. |

---

## 7. Space Agency Partner Data and Other References

**Data**
- Japan Meteorological Agency (JMA), RSMC Tokyo Best Track data (typhoon positions): https://www.jma.go.jp/jma/jma-eng/jma-center/rsmc-hp-pub-eg/Besttracks/bst_all.zip
- MAFF disaster damage statistics for paddy rice (the reference answer), via e-Stat: https://www.e-stat.go.jp/stat-search/files
- JMA AMeDAS ground observations (comparison of gusts, such as the 2019 typhoon): https://www.data.jma.go.jp/stats/etrn/view/
- NOAA CPC Oceanic Nino Index (ONI), used to test El Nino/La Nina: [TBD: confirm URL used in analyze_enso.py]
- ESA Sentinel-1 radar via Microsoft Planetary Computer (tried; did not detect lodging): https://planetarycomputer.microsoft.com/api/stac/v1
- MAFF Fude Polygon (field boundaries), used in the failed field-level attempt: [TBD: official MAFF page URL]
- Harvest timing guidance: Chiba Prefecture, https://www.pref.chiba.lg.jp/ninaite/gijyututaisaku/documents/240718harvest.pdf ; Ibaraki Prefecture, https://www.pref.ibaraki.jp/nourinsuisan/ounourin/keiei/fukyuuhp/documents/240820seiikujouhou05.pdf

**Libraries and tools:** Python, uv, httpx, NumPy, pandas, SciPy, scikit-learn, xarray, netCDF4, pystac-client, planetary-computer, odc-stac, rioxarray, GeoPandas, Matplotlib, MicroPython, Thonny / mpremote.

---

<!-- ============ ここから下は提出時に削除する ============ -->

## 日本語メモ（提出時に確認すること）

このメモは提出ページに貼らない。

### A. 埋める TBD の一覧
| 箇所 | 内容 | 担当 |
|---|---|---|
| §3 | YouTube の公開リンク（ログイン不要） | オーナー |
| §3 | 公開リポジトリのリンク（現在リポジトリは非公開。公開が必須） | オーナー |
| §4 Tools | 解決済み: `make_promo.py` を確認し、ffmpeg と Windows SAPI（Zira 優先の英語音声）と記載。Zira が入っていない環境では別の英語音声になるため、実際に使われた声名は動画生成時の `voice:` 出力で要確認 | 本体 |
| §7 | NOAA CPC の ONI の URL（`analyze_enso.py` に URL の記述が見つからなかった） | 本体 |
| §7 | 筆ポリゴンの公式ページ URL（`fetch_fude.py` は ArcGIS の REST を使っており、一般向けページが未確認） | 本体 |
| §1 | プロジェクト名の最終決定 | オーナー |
| §5 | 提出フォームの SI 欄にも同趣旨を書く。リポジトリ README にも SI 使用と動画の TTS を書く（`review-past-winners.md` の方針） | 本体 |
| 全体 | メンバー名・連絡先は入れていない。必要ならフォームの別欄 | オーナー |

### B. 数字の出典対応表
| 英語本文の数字 | 出典 |
|---|---|
| 23 台風（2004〜2021 年 8〜9 月、300 km 以内）、被害 100 ha 以上 7、被害なし 16 | `docs/priorities.md` §3、`docs/report.md` §1 |
| 16 中 10 で safe to wait、見逃し 1/7（2019 年 15 号）、格子の風 6.9 m/s | `docs/priorities.md` §3、`docs/report.md` §3、`docs/review-fable-5.2.md` A2 |
| 全国 1,815 行・86 台風、AUC 0.82 → 0.88 | `docs/priorities.md` §3、`docs/report.md` §2 |
| 閾値 約 17%（茨城・千葉 0.1674） | `docs/review-fable-5.2.md` P3・M1、`docs/pico.md` |
| 出穂後 400〜1,500℃ | `docs/priorities.md` §0・§3、`docs/review-fable-5.2.md` |
| 作付け比較 54／56／38／57（113 台風、1981〜2025 年、7〜10 月、35.9N 140.2E） | `results/planting_report.txt` A 表、`docs/review-past-winners.md` |
| 作付け比較の注意（出穂は気温のみ、1 地点、重なりは被害ではない） | `results/planting_report.txt` の注意①〜⑤ |
| Pico: 0.6〜1.2 ms、RAM 264 KB、23/23 一致、10 シナリオで判断と % 一致 | `docs/pico.md` |
| 収穫適期の目安 出穂後 35〜40 日（千葉は 38 日）、早刈りで未熟粒増・等級低下 | `docs/story.md` の公的資料の表 |
| Sentinel-1 相関 約 0.05、筆ポリゴン平均でも効かず | `docs/problem.md` §3 |
| ENSO と関係なし（1981〜2026 年） | `docs/priorities.md` §3 |
| IMERG Final V07・Late、POWER 変数 T2M・WS10M_MAX、GEOS-FP URL | `build_japan_dataset.py`、`fetch_imerg.py`、`fetch_geos_forecast.py`、`predict_lodging.py` |

### C. 確認できなかった・食い違い
1. **PC の 1 回の計算時間「2 µs」**: リポジトリの資料に該当値がなく、`docs/review-fable-5.2.md` M4 と `docs/report.md` は「0.1 ms 未満」。英語本文は「a few microseconds」とぼかした。実測値が確定していれば差し替えること。
2. **輪作比較の扱い**: `docs/priorities.md` §2 は「輪作の比較」を捨てるものとし、§5 でも「未実装。展望」としている。一方 `docs/review-fable-5.2.md` R1 と `docs/review-past-winners.md` は、作付け 4 通りの試算を済みとし、提出ページで使う方針。今回は依頼と後者に従い「簡易推定・展望への第一歩」として載せ、稲の中の品種・田植え日の選択であって輪作ではない、と明記した。priorities.md の更新が必要かもしれない。
3. 「e=+0.65」「Fisher p 値」「県の補正の値」は意図的に本文に載せていない（p 値を前に出さない方針）。聞かれたら p=0.045（統一モデル）、p=0.12（茨城・千葉の規則）。
4. 農家の友人は「a farmer we know」と抽象化した。公的資料の収穫適期は友人のヒアリングと別の根拠として併記した。
5. Faxai（ファクサイ）という名称は 2019 年 15 号の国際名で、リポジトリの資料には出てこない（私の知識による）。不安なら本文から削除すること。
6. チーム名が「Windfall Rice」であること、お題が Field Shift であることは依頼文と `docs/priorities.md` による。
7. 動画の TTS 表示（動画内の「Voice: AI-generated (TTS)」と MP4 metadata）は、`docs/promo/README.md` の要件による。提出ページ（§5）にも書いた。
