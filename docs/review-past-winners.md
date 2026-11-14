# 過去の受賞作との比較レビュー

2026-11-15 未明。根拠: お題 Field Shift の本文、Judging & Awards Guide（5 項目 × 1〜5 点）、NASA の 2024・2025 Global Winners 発表（いずれも公式ページをブラウザで確認）。受賞作は発表文の要約しか見ていない（中身の検証の深さは不明）。

## 農業系の過去の受賞作
| 年 | チーム（作品） | 賞 | お題 | 中身（発表文の要約） |
|---|---|---|---|---|
| 2024 | GaamaRamma（Waterwise） | Best Use of Data | Leveraging Earth Observation Data for Informed Agricultural Decision-Making | 干ばつ・病害虫の中で農家の水管理を助ける |
| 2024 | NVS-knot（2plant） | Galactic Impact | 同上 | 土壌水分と蒸発散で植え付け条件を評価し、植え付けリスクを管理するアプリ |
| 2025 | Twisters（SkySense） | Best Use of Technology | Will It Rain on My Parade? | NASA の地球観測＋AI で、雨・風などのリスクを評価し、安全な時間帯を提案する |
| 2025 | Zumorroda-X | Art & Technology | NASA Farm Navigators | 農家が熱波・洪水に適応する様子を学ぶミニゲーム |

- 共通点: 「NASA のデータ → 利用者のリスク評価 → 行動の提案」を、使える形（アプリ・ゲーム）で見せている
- 一番近いのは 2plant（植え付けのリスク）と SkySense（天気のリスクから安全な時間帯を出す）。Windfall Rice の「刈る／待ってよい」は同じ型
- 農業系のお題からは 2024 年に 2 作が世界受賞。題材として不利ではない

## 審査 5 項目での見立て（本体の主観）
| 項目 | 見立て | 理由 |
|---|---|---|
| Validity（科学的妥当性・実現性） | **強い** | 正解データ（農水省の統計）で 1 つ抜き検証、限界と失敗（SAR で見えなかった）を明示、PC・ブラウザ・Pico で判断一致。発表文を見る限り、受賞作でも検証の数字まで示した例は目立たない |
| Impact | 中 | 題材は日本の稲と台風で狭い。「手順ごと再利用できる（地域・作物・災害を差し替え）」が言えれば上がる |
| Creativity | 中 | 式はロジスティック回帰で新しくない。新しさは「農家の制約（計算資源なし・ロックインなし）から逆算した設計」と「数百円のマイコンで動く」点 |
| Relevance（お題との一致・NASA データの中心性） | **弱点** | お題は「輪作の選択で土の健康と気候への適応を助ける意思決定支援」。こちらの主題は収穫判断。NASA データ（GPM IMERG・NASA POWER）は中心にあり、そこは強い |
| Presentation | 未定 | 30 秒動画と英語の提出ページ次第 |

## 弱点（Relevance）の埋め方 — お題の本文の言葉を使う
お題の本文に、こちらの成果がそのまま当てはまる文がある。提出ページと動画で、この言葉を引用して対応づける。
- 「Your tool may highlight … **seasons when current crops appear more vulnerable**」→ 出穂後 400〜1,500℃（弱い時期）と台風期の重なり
- 「You may **compare at least three rotation strategies, including the existing rotation**」→ 作付け 4 通りの試算（今のやり方 54／田植えを遅らせる 56／早生 38／晩生 57、113 台風中）
- 「**does not replace farmer judgment**」→ 意思決定支援
- お題が挙げる NASA データに **GPM と NASA POWER** が入っている
- 届いていない部分（土の健康・水・輪作の作物の組み合わせ）は、限界として正直に書く

## 提出までに足りないもの（優先順）
1. **英語の提出ページ**（必須・未着手）: High-Level Summary、Detailed Description、NASA Data、References、SI の使用。審査は主にこのページで決まる（デモは一部）
2. **SI（AI）の使用の明記**: コード・解析の大半を Claude（Claude Code）で作った。規定上「コードとデータは説明文とメタデータで明記」。SI 欄（審査には見えない）だけでなく、提出ページの説明文とリポジトリの README にも書く。動画の TTS も同様
3. **公開リンク**: 最終成果物のリンクは公開が必須。リポジトリは非公開
4. 動画の原稿の最後を、お題の言葉に寄せる（例: 「It shows when current crops are most vulnerable, and compares planting strategies」）
