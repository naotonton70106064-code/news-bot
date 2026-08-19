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
