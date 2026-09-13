"""既存の記事 JSON / collected_urls.json をローカル PostgreSQL に移行する。

対象:
  - articles/{category}/*.json  (現行・カテゴリ別)
  - articles/*.json             (旧構造・IT のみ)
  - news_*.json                 (初期レガシー・リポジトリ直下)
  - collected_urls.json         → seen_urls

冪等性:
  articles には url の UNIQUE 制約が無く、意図的な URL 重複も投入するため
  UPSERT で冪等にはできない。代わりに投入前に両テーブルの件数を確認し、
  空でなければ中断する。入れ直す場合は --truncate を指定する。
  seen_urls は url が主キーなので ON CONFLICT で更新する。
  読み込み〜投入は 1 トランザクションで行い、途中失敗時は全てロールバックする。

使い方:
  python migrate_to_db.py                       # 全件投入 (テーブルが空でないと中断)
  python migrate_to_db.py --truncate            # 両テーブルを空にしてから全件投入
  python migrate_to_db.py --file articles/it/2026-09-12.json
  python migrate_to_db.py --limit 10
  python migrate_to_db.py --dry-run             # 変換結果を表示するだけ
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from db import get_connection
from render import parse_legacy_summary

JST = timezone(timedelta(hours=9))

ARTICLE_GLOBS = [
    "articles/*/*.json",
    "articles/*.json",
    "news_*.json",
]
COLLECTED_URLS_FILE = "collected_urls.json"

# ファイル名から article_date を導出する
DATE_PATTERNS = [
    re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.json$"),
    re.compile(r"^news_(\d{4})(\d{2})(\d{2})\.json$"),
]

INSERT_ARTICLE = """
INSERT INTO articles (
    url, title, japanese_title, category, article_date,
    summary_lines, points, prediction, ai_interpretation,
    background, market_impact, source, collected_at,
    legacy_summary, source_file
) VALUES (
    %(url)s, %(title)s, %(japanese_title)s, %(category)s, %(article_date)s,
    %(summary_lines)s, %(points)s, %(prediction)s, %(ai_interpretation)s,
    %(background)s, %(market_impact)s, %(source)s, %(collected_at)s,
    %(legacy_summary)s, %(source_file)s
)
"""

INSERT_SEEN_URL = """
INSERT INTO seen_urls (url, collected_at)
VALUES (%(url)s, %(collected_at)s)
ON CONFLICT (url) DO UPDATE SET collected_at = EXCLUDED.collected_at
"""


# ---------------------------------------------------------------------------
# 変換ヘルパー
# ---------------------------------------------------------------------------
def date_from_filename(path):
    name = os.path.basename(path)
    for pat in DATE_PATTERNS:
        m = pat.match(name)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise ValueError(f"ファイル名から日付を導出できません: {path}")


def parse_collected_at(value):
    """ISO8601 文字列を aware datetime に。naive なら JST として解釈する。"""
    if not value:
        return None
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


def text_or_none(value):
    if value is None:
        return None
    s = str(value)
    return s if s.strip() else None


def jsonb_or_none(value):
    if not value:
        return None
    return Jsonb(list(value))


def to_row(article, source_file):
    """JSON 1 件を articles テーブルの 1 行 (dict) に変換する"""
    url = text_or_none(article.get("url"))
    title = text_or_none(article.get("title"))
    if not url or not title:
        raise ValueError(f"url/title が欠損しています: {source_file} {article!r:.120}")

    summary_lines = article.get("summary_lines")
    background = article.get("background")
    legacy_summary = None

    # 旧スキーマ (title/url/source/summary/collected_at のみ)
    if not summary_lines and article.get("summary"):
        legacy_summary = str(article["summary"])
        legacy_lines, legacy_bg = parse_legacy_summary(legacy_summary)
        summary_lines = legacy_lines
        if not text_or_none(background):
            background = legacy_bg

    return {
        "url": url,
        "title": title,
        "japanese_title": text_or_none(article.get("japanese_title")),
        "category": text_or_none(article.get("category")),
        "article_date": date_from_filename(source_file),
        "summary_lines": jsonb_or_none(summary_lines),
        "points": jsonb_or_none(article.get("points")),
        "prediction": text_or_none(article.get("prediction")),
        "ai_interpretation": text_or_none(article.get("ai_interpretation")),
        "background": text_or_none(background),
        "market_impact": text_or_none(article.get("market_impact")),
        "source": text_or_none(article.get("source")),
        "collected_at": parse_collected_at(article.get("collected_at")),
        "legacy_summary": legacy_summary,
        "source_file": source_file,
    }


# ---------------------------------------------------------------------------
# 読み込み
# ---------------------------------------------------------------------------
def list_article_files(only_file=None):
    if only_file:
        return [only_file.replace("\\", "/")]
    files = []
    for pattern in ARTICLE_GLOBS:
        files.extend(sorted(p.replace("\\", "/") for p in glob.glob(pattern)))
    return files


def load_article_rows(files, limit=None):
    rows = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"トップレベルが配列ではありません: {path}")
        for article in data:
            rows.append(to_row(article, path))
            if limit is not None and len(rows) >= limit:
                return rows
    return rows


def load_seen_url_rows(path=COLLECTED_URLS_FILE):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} は辞書形式 {{url: collected_at}} である必要があります")
    return [{"url": url, "collected_at": parse_collected_at(ts)} for url, ts in data.items()]


# ---------------------------------------------------------------------------
# 投入
# ---------------------------------------------------------------------------
def count_rows(cur, table):
    return cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def summarize(rows):
    """変換結果の概要 (dry-run / 投入後の確認用)"""
    by_cat = {}
    by_file_dir = {}
    legacy = sum(1 for r in rows if r["legacy_summary"] is not None)
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
        d = os.path.dirname(r["source_file"]) or "."
        by_file_dir[d] = by_file_dir.get(d, 0) + 1
    return by_cat, by_file_dir, legacy


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="この JSON ファイルだけを投入する")
    ap.add_argument("--limit", type=int, help="先頭 N 件だけを投入する")
    ap.add_argument("--truncate", action="store_true", help="投入前に articles / seen_urls を TRUNCATE する")
    ap.add_argument("--dry-run", action="store_true", help="変換結果を表示するだけで DB に書き込まない")
    ap.add_argument("--skip-seen-urls", action="store_true", help="seen_urls への投入を行わない")
    args = ap.parse_args()

    files = list_article_files(args.file)
    print(f"対象ファイル: {len(files)} 件")
    article_rows = load_article_rows(files, args.limit)
    seen_rows = [] if args.skip_seen_urls else load_seen_url_rows()
    by_cat, by_dir, legacy = summarize(article_rows)
    print(f"記事 {len(article_rows)} 件 (旧スキーマ {legacy} 件) / seen_urls {len(seen_rows)} 件")
    print(f"  カテゴリ別: {by_cat}")
    print(f"  ディレクトリ別: {by_dir}")

    if args.dry_run:
        for r in article_rows[:3]:
            preview = {k: (v.obj if isinstance(v, Jsonb) else v) for k, v in r.items()}
            print(json.dumps(preview, ensure_ascii=False, default=str, indent=1)[:1200])
        print("--dry-run のため DB には書き込みません")
        return 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            existing_articles = count_rows(cur, "articles")
            existing_seen = count_rows(cur, "seen_urls")
            if args.truncate:
                print(f"TRUNCATE: articles {existing_articles} 件 / seen_urls {existing_seen} 件 を削除します")
                cur.execute("TRUNCATE articles RESTART IDENTITY")
                cur.execute("TRUNCATE seen_urls")
            elif existing_articles or existing_seen:
                print(
                    f"中断: articles に {existing_articles} 件 / seen_urls に {existing_seen} 件 が既に存在します。\n"
                    "  二重投入を避けるため何もしません。入れ直す場合は --truncate を指定してください。",
                    file=sys.stderr,
                )
                conn.rollback()
                return 1

            cur.executemany(INSERT_ARTICLE, article_rows)
            if seen_rows:
                cur.executemany(INSERT_SEEN_URL, seen_rows)

            after_articles = count_rows(cur, "articles")
            after_seen = count_rows(cur, "seen_urls")
            if after_articles != len(article_rows):
                raise RuntimeError(f"articles 件数不一致: 期待 {len(article_rows)} 実際 {after_articles}")
        conn.commit()

    print(f"投入完了: articles {after_articles} 件 / seen_urls {after_seen} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
