"""既存の記事ページ HTML を JSON から再生成するワンショット／冪等スクリプト。

記事ページは JS 描画からサーバサイド（生成時）レンダリングへ移行したため、
過去に生成済みの HTML も同じ方式で作り直して「JS を実行しなくても本文が
HTML ソースに存在する」状態にそろえる。

対象:
  - articles/{category}/YYYY-MM-DD.json  -> articles/{category}/YYYY-MM-DD.html
  - articles/YYYY-MM-DD.json（旧IT構造）  -> articles/YYYY-MM-DD.html

リポジトリ直下の dashboard_YYYYMMDD.html は articles/YYYY-MM-DD.html と
内容が完全重複していたため削除済み（どこからもリンクされていなかった）。

実行: python rebuild_article_pages.py
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from render import (
    ALL_CATEGORIES,
    TEMPLATE_PATH,
    build_related_links,
    render_page,
)


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, list) else None


def write_page(out_path, articles, date_str, category, related, depth, template):
    html = render_page(
        articles, date_str, category, related=related, depth=depth, template=template
    )
    out_path.write_text(html, encoding="utf-8")


def rebuild_one(category, date_str, template=None):
    """指定カテゴリ・指定日のページを JSON から作り直す。

    関連リンクは呼び出し時点のファイル存在状況で再計算されるため、
    他カテゴリや翌日のファイルが揃ったあとに呼べば、欠けていたリンクが埋まる。
    JSON が無い／壊れている場合は何もせず False を返す。
    """
    cat_dir = Path("articles") / category
    articles = load_json(cat_dir / f"{date_str}.json")
    if not articles:
        return False
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    related = build_related_links(date_str, category)
    write_page(
        cat_dir / f"{date_str}.html", articles, date_str, category, related, 2, template
    )
    return True


def _previous_article_date(category, date_str, max_back=366):
    """date_str より前で記事JSONが存在する最も近い日付を返す。無ければ None。"""
    try:
        current = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    cat_dir = Path("articles") / category
    for delta in range(1, max_back + 1):
        cand = (current - timedelta(days=delta)).strftime("%Y-%m-%d")
        if (cat_dir / f"{cand}.json").exists():
            return cand
    return None


def refresh_related_links(date_str, categories=None):
    """指定日の全カテゴリと、その直前の記事日のページを作り直す。

    main.py はカテゴリを順に処理するため、先に生成されるカテゴリのページは
    まだ存在しない他カテゴリへの「同じ日の他カテゴリ」リンクを張れない。
    また前日のページは、生成された時点で当日のファイルが無いため
    「翌日の記事へ」を持てない。日次実行の最後にこれを呼ぶと両方が埋まる。

    この穴は 2026-10-09 に発覚した。冪等なはずの rebuild_article_pages.py を
    実行したら74ページに差分が出たのが発見のきっかけで、原因は出力が
    カテゴリの処理順に依存していたこと。エラーにならないため気づけなかった。

    返り値は作り直したページのパス文字列のリスト。
    """
    if categories is None:
        categories = ALL_CATEGORIES
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    updated = []

    # 1. 当日 — 全カテゴリのファイルが揃った状態で「同じ日の他カテゴリ」を埋める
    for category in categories:
        if rebuild_one(category, date_str, template):
            updated.append(f"articles/{category}/{date_str}.html")

    # 2. 直前の記事日 — 当日のファイルができたので「翌日の記事へ」を埋める
    for category in categories:
        prev = _previous_article_date(category, date_str)
        if prev and rebuild_one(category, prev, template):
            updated.append(f"articles/{category}/{prev}.html")

    return updated


def main():
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    articles_root = Path("articles")
    count = 0

    # 1. 現行構造: articles/{category}/YYYY-MM-DD.json
    for category in ALL_CATEGORIES:
        cat_dir = articles_root / category
        if not cat_dir.exists():
            continue
        for json_file in sorted(cat_dir.glob("*.json")):
            date_str = json_file.stem
            articles = load_json(json_file)
            if not articles:
                continue
            related = build_related_links(date_str, category)
            write_page(
                cat_dir / f"{date_str}.html",
                articles,
                date_str,
                category,
                related,
                2,
                template,
            )
            count += 1
        print(f"  [{category}] 再生成完了")

    # 2. 旧IT構造: articles/YYYY-MM-DD.json
    for json_file in sorted(articles_root.glob("*.json")):
        date_str = json_file.stem
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
            continue
        articles = load_json(json_file)
        if not articles:
            continue
        write_page(
            articles_root / f"{date_str}.html",
            articles,
            date_str,
            "it",
            None,
            1,
            template,
        )
        count += 1
    print("  [legacy/articles直下] 再生成完了")

    print(f"記事ページを {count} 件再生成しました")


if __name__ == "__main__":
    main()
