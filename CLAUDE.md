# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

RSS フィードから取得したニュース記事を Anthropic Claude API で日本語要約し、GitHub Pages 上の静的サイトとして公開する自動化パイプライン。`it` / `japan_economy` / `world_economy` の 3 カテゴリを毎日収集する。GitHub Actions が毎日 04:00 JST に `main.py`、毎週月曜 05:00 JST に `weekly.py` を実行し、生成された HTML/JSON をコミットして Pages にデプロイする (`.github/workflows/daily.yml`, `weekly.yml`)。

## 主要コマンド

開発環境は Windows + `venv/`。Python は `venv/Scripts/python.exe` 経由で呼ぶ (CI は素の `python`)。

- 日次フルラン: `python main.py` — 収集 → 要約 → `articles/{category}/YYYY-MM-DD.{json,html}` を生成
- インデックス再生成: `python generate_index.py` — `articles/` を走査して `index.html` を作り直す
- 週次サマリー生成: `python weekly.py` — 前週分の記事を集約して `articles/{category}/weekly-YYYY-WNN.html` を作成
- 既存記事ページの再生成 (冪等): `python rebuild_article_pages.py` — `articles/` 以下と直下のレガシー HTML を JSON から作り直す。テンプレート (`templates/dashboard.html`) や `render.py` を変更したら実行する
- 既存記事への関連リンク再注入 (ワンショット・**非推奨**): `python update_related_links.py` — JS 描画時代の旧テンプレート向け。現行のサーバサイド生成ページには実行しないこと
- 既存記事へのフッターリンク注入 (ワンショット): `python add_footer_links.py` — 既存の `articles/` 以下全 HTML (旧構造含む) にプライバシーポリシー等へのフッターリンクを冪等に挿入/更新。新規生成分は `templates/dashboard.html` / `weekly.py` のテンプレートに同ブロックが組み込み済み
- 依存: `pip install feedparser anthropic python-dotenv` (CI と同じ)
- `ANTHROPIC_API_KEY` を `.env` か環境変数で渡す必要がある (`summarizer.py` が起動時にロード)

単体テストの仕組みは無く、各スクリプトは `if __name__ == "__main__"` でローカル実行できる (例: `python collector.py` で収集だけを試せる、`python summarizer.py` で 1 件要約だけを試せる)。

## アーキテクチャ

### パイプライン
```
collector.py        →  main.py            →  generate_index.py
(RSS収集+重複除外)     (要約+記事HTML生成)     (一覧index.html生成)
                        ↓
                       summarizer.py
                       (Claude API呼び出し)
```
週次は別経路: `weekly.py` が直近週の JSON を集約して `weekly-*.html` を出力 → `generate_index.py` が拾う。

### カテゴリ定義は `collector.py` の `FEEDS` 一つ
- `FEEDS[category]["sources"]` が各 RSS の URL/`limit`/`filter` を持つ
- `filter: True` のソース (Wired, Ars Technica) には IT キーワードフィルタ (`_matches_it_keywords`) が適用される。英語は `\b...\b` 単語境界、日本語は部分一致で `IT_KEYWORDS_EN` / `IT_KEYWORDS_JA` を判定
- カテゴリを追加するときは `FEEDS`、`main.py:ALL_CATEGORIES`、`generate_index.py:CATEGORIES`、`weekly.py:CATEGORIES` の 4 か所を揃える

### 重複除外 (`collected_urls.json`)
`collector.load_collected_urls()` が辞書 `{url: collected_at_iso}` 形式で URL を保持。**旧形式 (URL のリスト) は自動で辞書に移行される** ので、形式を変える場合はこの後方互換に注意。新規取得 URL は `collect_all()` 終了時に追記保存される。

### 要約フォーマットは `【...】` セクションマーカーで連結している
`summarizer.PROMPTS` はカテゴリ別テンプレートで、`【日本語タイトル】`/`【3行要約】`/`【背景・経緯】` (IT) または `【市場への影響】` (経済) /`【注目ポイント】`/`【今後の予測】`/`【AIの解釈】` を出力させる。`main.parse_summary()` はこのマーカーを境界としてセクションを切り出すので、**プロンプトのマーカーを変えたら `parse_summary` も同時に更新する**。IT には `background`、経済カテゴリには `market_impact` フィールドが入る非対称なスキーマで、`main.process_category` と `weekly.generate_weekly_summary` (ranked のソートキー) がこの差を意識している。

### HTML はすべて生成時にサーバサイドレンダリングする (SSR)
**JS を実行しなくても記事テキストが HTML ソースに存在する状態を必ず保つこと。** 以前は記事データを `<script>` 内の JS 変数に持たせ DOM を組み立てていたが、AdSense の審査 bot に「コンテンツのない空ページ」と判定されたため全ページを静的化した。

- `render.py` が記事ページのレンダラ (テンプレート = `templates/dashboard.html`)。テンプレートは**公開ルートに置かない** — 未置換のプレースホルダのままの空ページが GitHub Pages から配信され、審査 bot に空ページと見なされるため。`__PAGE_TITLE__` / `__META_DESCRIPTION__` / `__HEADING__` / `__DATE_TEXT__` / `__ARTICLE_COUNT__` / `__ARTICLES_HTML__` / `__RELATED_HTML__` / `__BACK_HREF__` / `__ROOT__` を置換する。`__ROOT__` はルートまでの相対パス (`depth` から算出、`articles/{cat}/x.html` は 2、`articles/x.html` は 1、リポジトリ直下は 0)
- `render.normalize_article()` が新旧スキーマ (`summary_lines`/`background`/`market_impact` と旧 `summary` 生テキスト) を吸収する。テキストは `esc()` でエスケープしてから `**強調**` を `<strong>` に変換する
- `main.generate_article_page` (新規) と `rebuild_article_pages.py` (既存分) が同じ `render.render_page()` を呼ぶので、テンプレート変更後は後者を実行して全ページをそろえる
- `generate_index.py` は各カテゴリの全週を `<section class="week-panel" data-cat data-page data-label>` として全部 HTML に書き出し、初期表示 (it の最新週) 以外に `hidden` を付ける。JS は既存 DOM の `hidden` を切り替えるだけ (カテゴリタブ・週送り) で、記事データを JS 側に持たない
- 各ページの `<noscript>` は折りたたみ/非表示を強制解除するので、JS 完全無効でも全内容が見える
- `weekly.py` は元から静的 HTML を出力しており変更不要

### 関連リンクのロジック
`render.build_related_links()` が正 (`main.py` はここから import する)。`update_related_links.py` にも旧実装のコピーが残るが**非推奨**で、現行テンプレートの出力に対して実行してはいけない。

### ディレクトリ構造の互換性
- 現行: `articles/{category}/{YYYY-MM-DD}.{json,html}` および `articles/{category}/weekly-{YYYY-WNN}.html`
- 旧構造: `articles/{YYYY-MM-DD}.{json,html}` (IT 専用、初期実装の名残)。`generate_index` はこれを IT の週に統合するが、リンク先は `articles/{date}.html` (旧パス) のまま出す — `articles/it/{date}.html` は存在しないので混同しないこと
- `weekly.load_week_articles` は IT カテゴリのときだけ旧構造も追加で読み込む。`news_YYYYMMDD.json` (リポジトリ直下) は初期化期のレガシーデータで、現行パイプラインからは触らない (`articles/{date}.json` と内容が重複)。対になっていた `dashboard_YYYYMMDD.html` は重複コンテンツだったため削除済み — 再生成しないこと

### GitHub Actions の責務
両ワークフローとも (1) スクリプト実行、(2) `articles/`・`index.html`・`collected_urls.json` を `git add` してコミット&push、(3) 「公開対象から templates/ を除外」ステップで作業ツリーの `templates/` を `$RUNNER_TEMP` へ退避、(4) リポジトリ全体 (`path: '.'`) を Pages アーティファクトとして upload &deploy、を行う。差分がなければコミットはスキップされる (`git diff --staged --quiet || git commit`)。

**upload の前に必ず `templates/` を退避すること。** `path: '.'` でリポジトリ全体が配信されるため、退避しないと未置換プレースホルダのままのテンプレートが `/templates/dashboard.html` として公開される。退避はコミット&push の後に行うのでリポジトリの内容には影響せず、除外ステップは `index.html` / `articles/` の存在も併せて検証している (欠落したらジョブが失敗する)。
