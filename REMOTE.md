# 外出先から Claude Code を使うガイド

ハッカソン会場などに、スマホやノート PC だけを持って行っても作業を続けるための手引きです。2026-11-09 時点で公式ドキュメントを調べた内容をもとにしています。画面のボタン名やメニューの位置は変わることがあるので、見つからないときは近い名前のものを探してください。

## 1. まずは3行で

- 本番は **B（クラウドセッション）をメイン**にします。家の PC が停電やスリープ、Windows Update の再起動で止まっても、作業を続けられるからです。
- **A（Remote Control）** は、家の PC がついているとわかっているときの予備にします。
- **出かける前に、家で一度 B を通しで試す**ことが、いちばん大事です。

## 2. 3つの方法をくらべる表

| | A. Remote Control | B. クラウドセッション | C. teleport |
|---|---|---|---|
| たとえると | 家の PC を、スマホでリモコン操作する | Anthropic のパソコンを借りる | クラウドでやった作業を、家の PC に持ち帰る |
| 何で動く | 家の PC | Anthropic のクラウド | 家の PC（作業内容はクラウドから受け取る） |
| 家の PC の電源 | 入れたままにする（スリープすると切れる） | 切っても大丈夫 | 持ち帰るときに使う |
| NASA API キーの置き場所 | 家の PC の `.env`（そのまま使える） | 環境設定の Environment variables | 家の PC の `.env` |
| 向いている場面 | 家の PC がついているとわかっているとき | 本番のメイン。PC が止まるかもしれないとき | クラウドで進めた作業を家で続けたいとき |

用語の説明です。

- **API キー**: NASA のデータを使うための「合いかぎ」です。
- **リポジトリ**: プログラムのファイルをまとめて保存する入れ物です。ここでは GitHub 上にあります。
- **push**: 家の PC の変更を GitHub に送ることです。
- **プルリクエスト（PR）**: 「この変更を取り込んでください」というお願いです。

## 3. 出かける前のチェックリスト

- [ ] GitHub に push 済み
- [ ] スマホに Claude アプリを入れてログイン
- [ ] Claude GitHub App（GitHub と Claude をつなぐ公式アプリ）を非公開リポジトリに入れる
- [ ] クラウド環境の Network を Custom にして `api.nasa.gov` を追加
- [ ] Environment variables に `NASA_API_KEY` を追加
- [ ] 家で、クラウドセッションに「`uv run neows.py --days 1` を実行して」と頼み、表が出るか確かめる
- [ ] Remote Control も1回試す
- [ ] Windows のスリープを「なし」にする（A を使う場合）

## 4. B（クラウド）の使い方

1. GitHub にある非公開リポジトリを使うため、Claude GitHub App をインストールします（または Claude Code で `/web-setup` を実行します）。
2. claude.ai/code か、スマホアプリの Code タブを開きます。
3. 環境の設定で Network access を **Custom** にします。ネットワークの既定は「Trusted」で、パッケージ置き場や GitHub などにしかつながりません。**`api.nasa.gov` は既定では許可されていない**ので、1行ずつ追加します（`*.` でワイルドカードも使えます）。
   - 注意: Custom にしたとき、既定のリスト（PyPI など）も残るかは要確認です。uv で依存を入れる必要があるので、家で一度試してください。
4. 同じ環境設定の Environment variables に `NASA_API_KEY=キー` と書きます。この値は、その環境を使える人なら読めます。だから個人のアカウントで使ってください。
   - Network secrets という機能もありますが、これは「ヘッダー」という部分で鍵を渡す仕組みです。NASA はクエリ（URL の `?api_key=` の部分）で渡すので、使えるかは未確認です。
5. セッションを始めます。方法は次のどれかです。
   - claude.ai/code やアプリの Code タブから始める
   - 家の PC から `claude --cloud "やること"` を実行する（先に push しておきます）
   - Windows で `--cloud` を使うと、コミットしていない変更もそのままアップロードされます。`.env` は `.gitignore` に入っているので送られません。
6. やってほしいことを書いて頼みます。権限モードは Auto / Accept edits / Plan から選べます。
7. 終わったら Changes カードで結果を確認し、Create PR で GitHub にプルリクエストを作ります。

気をつけること:

- 家の `~/.claude/settings.json` は読まれません。だから、そこに書いた deny ルール（してはいけないことの禁止リスト）も効きません。リポジトリ内の `.claude/settings.json` は読まれます。
- しばらく放っておくと一時停止します。長く放置すると環境が回収され、会話は残りますが、動いていた処理は消えます。

## 5. A（Remote Control）の使い方

1. 家の PC の電源を入れたままにします。Windows の電源設定で、スリープを「なし」にします。
2. 作業フォルダで `claude --remote-control "nasa"` を実行します（`--rc` でも同じです）。すでに動いているセッションでは `/remote-control`（`/rc`）でも始められます。サーバーモードは `claude remote-control` です。
3. スマホからつなぎます。次のどれかを使います。
   - 表示された URL を開く
   - 表示された QR コードを読む
   - claude.ai/code か、スマホの Claude アプリの Code タブにあるセッション一覧から選ぶ
   - アプリが入っていなければ、`/mobile` で QR コードが出ます。
4. 家の PC にある `.env` や設定（deny ルールを含む）が、そのまま使えます。

使える条件は、Pro / Max などの個人プランです。

回線が切れたときは次のとおりです。

- 対話セッションは、回線が戻ると自動で再接続します。
- サーバーモードは、通信できない状態が約10分続くと終了します。
- 約30分つながらないと、`/remote-control` でつなぎ直す必要があります。
- 停止から約4時間以内なら、`claude remote-control --continue` で再開できます。

## 6. 作業を家に持ち帰る

次のどちらかを使います。

- **PR をマージして `git pull`**: GitHub で PR をマージし、家の PC で `git pull` します。いちばんわかりやすい方法です。
- **teleport（C）**: 家の PC で `claude --teleport` を実行するか、セッション内で `/teleport` を使います。
  - 条件: 作業中の変更がない（クリーン）こと、同じリポジトリであること、ブランチが push 済みであること、同じ claude.ai アカウントであること。
  - 一方通行です。家の PC からクラウドへ送る逆向きはできません。

## 7. 困ったとき

| 症状 | 原因 | どうする |
|---|---|---|
| NASA につながらない（クラウド） | `api.nasa.gov` が許可されていない（既定では許可されていません） | 環境の設定 → Network access を Custom にして、`api.nasa.gov` を追加する |
| キーがないと言われる、`DEMO_KEY` の警告が出る | Environment variables に `NASA_API_KEY` がない | 環境設定に `NASA_API_KEY=キー` を書く。家の PC なら `.env` を確認する |
| スマホの接続が切れた | 回線が切れた、または家の PC がスリープした | 対話セッションは復帰すると自動で再接続する。約30分つながらなければ `/remote-control` でつなぎ直す。サーバーモードは `claude remote-control --continue`（停止から約4時間以内） |
| 文字化け | 出力の文字コードが合っていない | `nasa_common.py` で UTF-8 に固定している。新しいスクリプトでもそれを使っているか確認する |
| `DEMO_KEY` の回数切れ | `DEMO_KEY` は制限が厳しい（30回/時・50回/日） | 自分のキーを https://api.nasa.gov で取り、`NASA_API_KEY` に設定する（個人キーは 1,000回/時） |

## 8. 出典（2026-11-09 時点）

- https://code.claude.com/docs/en/remote-control.md
- https://code.claude.com/docs/en/claude-code-on-the-web.md
- https://code.claude.com/docs/en/web-quickstart.md
- https://code.claude.com/docs/en/cloud-environments.md
- https://code.claude.com/docs/en/settings.md
- https://code.claude.com/docs/en/permissions.md
