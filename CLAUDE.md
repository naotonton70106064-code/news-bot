# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

RSS フィードから取得したニュース記事を Anthropic Claude API で日本語要約し、GitHub Pages 上の静的サイトとして公開する自動化パイプライン。`it` / `japan_economy` / `world_economy` の 3 カテゴリを毎日収集する。GitHub Actions が毎日 04:00 JST に `main.py`、毎週月曜 05:00 JST に `weekly.py` を実行し、生成された HTML/JSON をコミットして Pages にデプロイする (`.github/workflows/daily.yml`, `weekly.yml`)。

## 主要コマンド

開発環境は Windows + `venv/`。Python は `venv/Scripts/python.exe` 経由で呼ぶ (CI は素の `python`)。

- 日次フルラン: `python main.py` — 収集 → 要約 → `articles/{category}/YYYY-MM-DD.{json,html}` を生成
- インデックス再生成: `python generate_index.py` — `articles/` を走査して `index.html` を作り直す
- 週次サマリー生成: `python weekly.py` — 前週分の記事を集約して `articles/{category}/weekly-YYYY-WNN.html` を作成
- 既存記事への関連リンク再注入 (ワンショット): `python update_related_links.py` — 既存の `articles/{category}/*.html` に内部リンクセクションを冪等に挿入/更新
- 既存記事へのフッターリンク注入 (ワンショット): `python add_footer_links.py` — 既存の `articles/` 以下全 HTML (旧構造含む) にプライバシーポリシー等へのフッターリンクを冪等に挿入/更新。新規生成分は `dashboard.html` / `weekly.py` のテンプレートに同ブロックが組み込み済み
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

### HTML 生成はプレースホルダ置換テンプレート
`dashboard.html` は静的 HTML テンプレートで、`__ARTICLES__` (記事 JSON 配列) と `__RELATED_LINKS__` (前後日/他カテゴリ/週次へのナビ JSON) を JS の中に持つ。`main.generate_article_page` がこの 2 つを `json.dumps` で差し替えて `articles/{category}/{date}.html` として書き出す。テンプレートの構造を変えるときは `dashboard.html` 側 (CSS+JS) と差し替え後の参照位置 (line 92-93 付近) を同期させる。

### 関連リンクのロジックは 2 か所に複製されている
`main.build_related_links()` と `update_related_links.build_related_links()` は同一の意味を持つ実装。前者は新規記事 HTML 生成時に呼ばれ、後者は既存 HTML へのバックフィル用ワンショット。**仕様変更時は両方を直す必要がある** (片方だけ更新すると、新旧記事で挙動が分かれる)。

### ディレクトリ構造の互換性
- 現行: `articles/{category}/{YYYY-MM-DD}.{json,html}` および `articles/{category}/weekly-{YYYY-WNN}.html`
- 旧構造: `articles/{YYYY-MM-DD}.{json,html}` (IT 専用、初期実装の名残)
- `weekly.load_week_articles` は IT カテゴリのときだけ旧構造も追加で読み込む。`news_YYYYMMDD.json` / `dashboard_YYYYMMDD.html` (リポジトリ直下) も初期化期のレガシーで、現行パイプラインからは触らない

### GitHub Actions の責務
両ワークフローとも (1) スクリプト実行、(2) `articles/`・`index.html`・`collected_urls.json` を `git add` してコミット&push、(3) リポジトリ全体を Pages アーティファクトとして upload &deploy、を行う。差分がなければコミットはスキップされる (`git diff --staged --quiet || git commit`)。
