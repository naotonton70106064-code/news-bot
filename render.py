"""記事ページの HTML を生成時（サーバサイド）にレンダリングする共通モジュール。

JS に依存せず <body> 内へ記事本文が直接書き出されるようにするため、
templates/dashboard.html のプレースホルダを Python 側で埋める。
main.py（新規生成）と rebuild_article_pages.py（既存分の再生成）の両方から使う。
"""
import html as _html
import re
from datetime import datetime, timedelta
from pathlib import Path

# テンプレートは公開ルートに置かない（未置換のプレースホルダのまま配信されるため）
TEMPLATE_PATH = Path("templates") / "dashboard.html"

CATEGORY_DISPLAY_NAMES = {
    "it": "IT・テクノロジー",
    "japan_economy": "日本経済",
    "world_economy": "世界経済",
}

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]

ALL_CATEGORIES = ["it", "japan_economy", "world_economy"]


def build_related_links(date_str, category):
    """記事ページの関連リンク情報を構築する。
    存在するファイルのみリンク化する（前後日・他カテゴリ・週次サマリー）。"""
    articles_root = Path("articles")
    cat_dir = articles_root / category

    other_categories = []
    for other in ALL_CATEGORIES:
        if other == category:
            continue
        target = articles_root / other / "{}.html".format(date_str)
        if target.exists():
            other_categories.append({
                "key": other,
                "name": CATEGORY_DISPLAY_NAMES[other],
                "href": "../{}/{}.html".format(other, date_str),
            })

    try:
        current_dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        current_dt = None

    prev_link = None
    next_link = None
    if current_dt is not None and cat_dir.exists():
        for delta in range(1, 366):
            candidate = current_dt - timedelta(days=delta)
            cand_str = candidate.strftime("%Y-%m-%d")
            if (cat_dir / "{}.html".format(cand_str)).exists():
                prev_link = {"date": cand_str, "href": "{}.html".format(cand_str)}
                break
        for delta in range(1, 366):
            candidate = current_dt + timedelta(days=delta)
            cand_str = candidate.strftime("%Y-%m-%d")
            if (cat_dir / "{}.html".format(cand_str)).exists():
                next_link = {"date": cand_str, "href": "{}.html".format(cand_str)}
                break

    weekly = None
    if current_dt is not None:
        iso_year, iso_week, _ = current_dt.isocalendar()
        week_id = "{}-W{:02d}".format(iso_year, iso_week)
        weekly_file = cat_dir / "weekly-{}.html".format(week_id)
        if weekly_file.exists():
            weekly = {"id": week_id, "href": "weekly-{}.html".format(week_id)}

    return {
        "currentDate": date_str,
        "currentCategory": category,
        "otherCategories": other_categories,
        "prevDate": prev_link,
        "nextDate": next_link,
        "weekly": weekly,
    }


def esc(text):
    """HTML エスケープ"""
    if text is None:
        return ""
    return _html.escape(str(text), quote=True)


def rich(text):
    """エスケープした上で **強調** を <strong> に変換する（JS 版 cleanText 相当）"""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


def _is_valid_title(t):
    """タイトルとして有効か（空・記号のみは無効）"""
    if not t:
        return False
    s = str(t).strip()
    if not s:
        return False
    return not re.fullmatch(r"[-—ー―ｰ_=・\s]+", s)


def _has_content(t):
    return bool(t and str(t).strip())


def parse_legacy_summary(summary_text):
    """旧構造の summary（【3行要約】【背景・ポイント】の生テキスト）を分解する"""
    lines_out = []
    background = ""
    current = None
    for line in str(summary_text).split("\n"):
        line = line.strip()
        if not line:
            continue
        if "【3行要約】" in line:
            current = "summary"
        elif "【背景" in line:
            current = "background"
        elif line.startswith("【"):
            current = None
        elif current == "summary":
            lines_out.append(line)
        elif current == "background":
            background += line + " "
    return lines_out, background.strip()


def normalize_article(article):
    """新旧どちらのスキーマでも共通の描画用 dict に正規化する"""
    title = article.get("japanese_title")
    if not _is_valid_title(title):
        title = article.get("title", "")

    summary_lines = list(article.get("summary_lines") or [])
    background = article.get("background", "")
    background_label = "背景・経緯"
    points = list(article.get("points") or [])

    if not summary_lines and article.get("summary"):
        legacy_lines, legacy_bg = parse_legacy_summary(article["summary"])
        summary_lines = legacy_lines
        if not _has_content(background):
            background = legacy_bg
            background_label = "背景・ポイント"

    return {
        "display_title": title,
        "original_title": article.get("title", ""),
        "url": article.get("url", ""),
        "source": article.get("source", ""),
        "summary_lines": summary_lines,
        "background": background,
        "background_label": background_label,
        "market_impact": article.get("market_impact", ""),
        "points": points,
        "prediction": article.get("prediction", ""),
        "ai_interpretation": article.get("ai_interpretation", ""),
    }


def render_article_card(article, index):
    """記事1件分のカード HTML を返す"""
    a = normalize_article(article)

    summary_html = "".join(
        '<p class="summary-line">{}</p>'.format(rich(line))
        for line in a["summary_lines"]
    )
    points_html = "".join(
        '<p class="detail-point">{}</p>'.format(rich(p)) for p in a["points"]
    )

    sections = []
    if _has_content(a["background"]):
        sections.append(
            '<div class="detail-section">'
            '<div class="detail-label">{}</div>'
            '<div class="detail-text">{}</div>'
            "</div>".format(esc(a["background_label"]), rich(a["background"]))
        )
    if _has_content(a["market_impact"]):
        sections.append(
            '<div class="detail-section">'
            '<div class="detail-label">市場への影響</div>'
            '<div class="detail-text">{}</div>'
            "</div>".format(rich(a["market_impact"]))
        )
    if a["points"]:
        sections.append(
            '<div class="detail-section">'
            '<div class="detail-label">注目ポイント</div>'
            "{}"
            "</div>".format(points_html)
        )
    if _has_content(a["prediction"]):
        sections.append(
            '<div class="detail-section">'
            '<div class="detail-label">今後の予測</div>'
            '<div class="detail-text">{}</div>'
            "</div>".format(rich(a["prediction"]))
        )
    if _has_content(a["ai_interpretation"]):
        sections.append(
            '<div class="detail-section">'
            '<div class="ai-badge">AIの解釈</div>'
            '<div class="detail-text">{}</div>'
            "</div>".format(rich(a["ai_interpretation"]))
        )

    return (
        '      <article class="card">\n'
        '        <div class="card-main">\n'
        '          <div class="card-top">\n'
        '            <h2 class="title">{title}</h2>\n'
        '            <div class="source">{source}</div>\n'
        "          </div>\n"
        '          <div class="summary-lines">{summary}</div>\n'
        '          <button class="expand-btn" id="btn-{i}" aria-expanded="false" aria-controls="detail-{i}" onclick="toggle({i})">詳細を見る &#9662;</button>\n'
        "        </div>\n"
        '        <div class="detail" id="detail-{i}">\n'
        "          {sections}\n"
        '          <div class="detail-footer">\n'
        '            <a class="btn-link" href="{url}" target="_blank" rel="noopener">元記事を読む &rarr;</a>\n'
        "          </div>\n"
        "        </div>\n"
        "      </article>\n"
    ).format(
        title=esc(a["display_title"]),
        source=esc(a["source"]),
        summary=summary_html,
        sections="".join(sections),
        url=esc(a["url"]),
        i=index,
    )


def render_articles_html(articles):
    return "".join(render_article_card(a, i) for i, a in enumerate(articles))


def render_related_html(related):
    """関連リンクセクションの HTML を返す（リンクが無ければ空文字）"""
    if not related or not isinstance(related, dict):
        return ""

    groups = []

    others = related.get("otherCategories") or []
    if others:
        links = "".join(
            '<a class="related-link" href="{}">同じ日の{}を見る &rarr;</a>'.format(
                esc(o.get("href", "")), esc(o.get("name", ""))
            )
            for o in others
        )
        groups.append(
            '<div class="related-group">'
            '<div class="related-group-title">同じ日の他カテゴリ</div>'
            '<div class="related-links">{}</div>'
            "</div>".format(links)
        )

    prev = related.get("prevDate")
    nxt = related.get("nextDate")
    if prev or nxt:
        nav = ""
        if prev:
            nav += '<a class="related-link" href="{}">&larr; 前日の記事へ ({})</a>'.format(
                esc(prev.get("href", "")), esc(prev.get("date", ""))
            )
        if nxt:
            nav += '<a class="related-link" href="{}">翌日の記事へ ({}) &rarr;</a>'.format(
                esc(nxt.get("href", "")), esc(nxt.get("date", ""))
            )
        groups.append(
            '<div class="related-group">'
            '<div class="related-group-title">日付ナビ</div>'
            '<div class="related-nav-row">{}</div>'
            "</div>".format(nav)
        )

    weekly = related.get("weekly")
    if weekly and weekly.get("href"):
        groups.append(
            '<div class="related-group">'
            '<div class="related-group-title">週次サマリー</div>'
            '<div class="related-links">'
            '<a class="related-link related-link-weekly" href="{}">この週のまとめを見る ({}) &rarr;</a>'
            "</div></div>".format(esc(weekly["href"]), esc(weekly.get("id", "")))
        )

    if not groups:
        return ""

    return (
        '  <section class="related-section" id="related-section">\n'
        "    <h2>関連リンク</h2>\n"
        '    <div id="related-content">{}</div>\n'
        "  </section>\n"
    ).format("".join(groups))


def format_date_ja(date_str):
    """2026-08-19 -> ("2026年8月19日（水）", "2026年8月19日")"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return date_str, date_str
    wd = WEEKDAYS_JA[dt.weekday()]
    plain = "{}年{}月{}日".format(dt.year, dt.month, dt.day)
    return "{}（{}）".format(plain, wd), plain


def build_description(articles, cat_name, date_plain):
    """meta description 用のテキスト（先頭数件のタイトルを含める）"""
    titles = []
    for a in articles[:3]:
        t = normalize_article(a)["display_title"]
        if t:
            titles.append(t)
    text = "{}の{}ニュース{}件をAIが要約。".format(date_plain, cat_name, len(articles))
    if titles:
        text += "主な話題: " + "／".join(titles)
    return text[:160]


def render_page(articles, date_str, category, related=None, depth=2, template=None):
    """記事ページ HTML 全体を組み立てて返す。

    depth: リポジトリルートまでの階層数（articles/it/x.html なら 2、articles/x.html なら 1）
    """
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

    cat_name = CATEGORY_DISPLAY_NAMES.get(category, "ニュース")
    date_full, date_plain = format_date_ja(date_str)
    root = "../" * depth

    page_title = "{}の{}ニュースまとめ - AIニュースまとめ".format(date_plain, cat_name)
    heading = "{} {}のニュース".format(cat_name, date_plain)

    html = template
    html = html.replace("__PAGE_TITLE__", esc(page_title))
    html = html.replace(
        "__META_DESCRIPTION__", esc(build_description(articles, cat_name, date_plain))
    )
    html = html.replace("__HEADING__", esc(heading))
    html = html.replace("__DATE_TEXT__", esc(date_full))
    html = html.replace("__ARTICLE_COUNT__", str(len(articles)))
    html = html.replace("__ARTICLES_HTML__", render_articles_html(articles))
    html = html.replace("__RELATED_HTML__", render_related_html(related))
    html = html.replace("__BACK_HREF__", esc("{}index.html?cat={}".format(root, category)))
    html = html.replace("__ROOT__", root)
    return html
