"""設計ケーススタディ（人が手書きする Markdown 記事）を静的 HTML にビルドするスクリプト。

ニュース記事（RSS → JSON → render.py）とは別系統。ローカルで実行して生成物をコミットする
（CI は実行しない。CI の generate_index.py は case-studies/index.json を読むだけ）。

入力:  content/case-studies/NNN-slug.md      （frontmatter + Markdown。`_` 始まりは無視）
出力:  case-studies/NNN-slug/index.html      （記事ページ。URL は /case-studies/NNN-slug/）
       case-studies/index.html               （一覧ページ）
       case-studies/index.json               （マニフェスト。generate_index.py が読む）

frontmatter（YAML）:
  title, no（通し番号 = ファイル名の3桁連番と一致必須）, genre, date, xPostedAt（任意）,
  tags[]（任意）, ads（true/false: AdSense コードを出すか）, description（任意）

依存（ローカルのみ）: pip install markdown pygments pyyaml
実行: python build_case_studies.py
"""
import html as _html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import markdown
import yaml
from markdown.extensions.toc import slugify_unicode
from pygments.formatters import HtmlFormatter

from render import esc, render_ads_head, render_ads_unit

CONTENT_DIR = Path("content") / "case-studies"
OUTPUT_DIR = Path("case-studies")
TEMPLATE_PATH = Path("templates") / "case_study.html"
INDEX_TEMPLATE_PATH = Path("templates") / "case_studies_index.html"
MANIFEST_PATH = OUTPUT_DIR / "index.json"

# 一覧ページは他の一覧系ページ（index.html 等）と同じく head ローダのみ入れる
LISTING_ADS = True

FILENAME_RE = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
H1_RE = re.compile(r"^#\s+設計ケーススタディ\s*(\d+)\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^(`{3,}|~{3,})[^\n]*\n(.*?)\n\1[ \t]*$", re.MULTILINE | re.DOTALL)

REQUIRED_KEYS = ("title", "no", "genre", "date", "ads")
REQUIRED_H2 = (
    "Problem",
    "Question",
    "自分の回答",
    "なぜそう考えたか",
    "AIレビュー",
    "再考・気づき",
    "設計ポイント",
)

MD_EXTENSIONS = ["fenced_code", "codehilite", "tables", "toc", "sane_lists"]
MD_EXTENSION_CONFIGS = {
    # guess_lang=False: 言語未指定 / text のブロックを Pygments に推測させない（ASCII 図保護）
    "codehilite": {"guess_lang": False, "css_class": "codehilite", "linenums": False},
    # 見出しに id を付ける（日本語見出しも _1 ではなく読める id にする）
    "toc": {"permalink": False, "slugify": slugify_unicode},
}


class BuildError(Exception):
    pass


# ---------------------------------------------------------------------------
# 読み込み・検証
# ---------------------------------------------------------------------------
def split_frontmatter(text):
    """先頭の --- ... --- を YAML として切り出し、(meta dict, body) を返す"""
    if not text.startswith("---"):
        raise BuildError("frontmatter（先頭の ---）がありません")
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not m:
        raise BuildError("frontmatter の終端 --- が見つかりません")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise BuildError("frontmatter が辞書形式ではありません")
    # YAML 1.1 では裸の `no` が真偽値 False として読まれるため、キー名 no に戻す
    if False in meta and "no" not in meta:
        meta["no"] = meta.pop(False)
    return meta, text[m.end():]


def _to_iso_date(value, key):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return value.strip()
    raise BuildError("{} は YYYY-MM-DD 形式で指定してください: {!r}".format(key, value))


def _to_iso_datetime_or_none(value, key):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip()
    raise BuildError("{} の形式が不正です: {!r}".format(key, value))


def load_case_study(md_path):
    """1 記事を読み込んで検証し、正規化した dict を返す"""
    m = FILENAME_RE.match(md_path.name)
    if not m:
        raise BuildError("ファイル名は NNN-slug.md（3桁連番 + 半角英数字とハイフン）にしてください")
    file_no = int(m.group(1))
    slug = md_path.stem  # 例: 010-email-duplicate（URL のディレクトリ名）

    text = md_path.read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)

    missing = [k for k in REQUIRED_KEYS if k not in meta]
    if missing:
        raise BuildError("frontmatter に必須キーがありません: {}".format(", ".join(missing)))
    if not isinstance(meta["no"], int):
        raise BuildError("no は整数で指定してください: {!r}".format(meta["no"]))
    if meta["no"] != file_no:
        raise BuildError("frontmatter の no ({}) とファイル名の連番 ({}) が一致しません".format(meta["no"], file_no))
    if not isinstance(meta["ads"], bool):
        raise BuildError("ads は true / false で指定してください: {!r}".format(meta["ads"]))

    h1 = H1_RE.search(body)
    if not h1:
        raise BuildError("本文の h1 は「# 設計ケーススタディ NN: タイトル」の形式にしてください")
    if int(h1.group(1)) != file_no:
        raise BuildError("h1 の番号 ({}) とファイル名の連番 ({}) が一致しません".format(h1.group(1), file_no))

    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        raise BuildError("tags はリストで指定してください: {!r}".format(tags))

    h2s = re.findall(r"^##\s+(.+?)\s*$", body, re.MULTILINE)
    warnings = []
    for req in REQUIRED_H2:
        if not any(h.startswith(req) for h in h2s):
            warnings.append("必須見出し「## {}」がありません".format(req))

    return {
        "slug": slug,
        "no": file_no,
        "title": str(meta["title"]).strip(),
        "genre": str(meta["genre"]).strip(),
        "date": _to_iso_date(meta["date"], "date"),
        "xPostedAt": _to_iso_datetime_or_none(meta.get("xPostedAt"), "xPostedAt"),
        "tags": [str(t).strip() for t in tags],
        "ads": meta["ads"],
        "description": (str(meta["description"]).strip() if meta.get("description") else ""),
        "body_md": body,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------
def render_markdown(body_md):
    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS)
    html = md.convert(body_md)
    # 表は横にはみ出し得るので、ページではなく表だけをスクロールさせる
    html = html.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    return html


def verify_fences(body_md, html):
    """Markdown のフェンスブロック本文が HTML の <pre> にそのまま残っているか検証する。
    ASCII 図やコードが変換で壊れていたらビルドを失敗させる。"""
    fences = [f.group(2) for f in FENCE_RE.finditer(body_md)]
    pres = re.findall(r"<pre>(.*?)</pre>", html, re.DOTALL)
    if len(fences) != len(pres):
        raise BuildError("フェンスブロック数 ({}) と <pre> 数 ({}) が一致しません".format(len(fences), len(pres)))
    for i, (src, pre) in enumerate(zip(fences, pres), 1):
        rendered = _html.unescape(re.sub(r"<[^>]+>", "", pre))
        if rendered.rstrip("\n") != src.rstrip("\n"):
            raise BuildError("コードブロック #{} の内容が変換前後で一致しません".format(i))
    return len(fences)


def build_description(cs, body_html):
    if cs["description"]:
        return cs["description"][:160]
    text = re.sub(r"<pre>.*?</pre>", " ", body_html, flags=re.DOTALL)
    text = re.sub(r"<h1[^>]*>.*?</h1>", " ", text, flags=re.DOTALL)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    head = "設計ケーススタディ {}: {}。".format(cs["no"], cs["title"])
    return (head + text)[:160]


def format_date_ja(iso):
    y, m, d = iso.split("-")
    return "{}年{}月{}日".format(int(y), int(m), int(d))


def render_meta_html(cs):
    parts = [
        '      <span class="case-no">No. {:03d}</span>'.format(cs["no"]),
        '      <span class="case-genre">{}</span>'.format(esc(cs["genre"])),
        '      <span class="case-date">{}</span>'.format(esc(format_date_ja(cs["date"]))),
    ]
    for t in cs["tags"]:
        parts.append('      <span class="case-tag">#{}</span>'.format(esc(t)))
    if cs["xPostedAt"]:
        parts.append('      <span class="case-x">X 投稿: {}</span>'.format(esc(cs["xPostedAt"][:10])))
    return "\n".join(parts)


def render_related_html(prev_cs, next_cs):
    if not prev_cs and not next_cs:
        return ""
    nav = ""
    if prev_cs:
        nav += '<a class="related-link" href="../{}/">&larr; No. {:03d} {}</a>'.format(
            esc(prev_cs["slug"]), prev_cs["no"], esc(prev_cs["title"])
        )
    if next_cs:
        nav += '<a class="related-link" href="../{}/">No. {:03d} {} &rarr;</a>'.format(
            esc(next_cs["slug"]), next_cs["no"], esc(next_cs["title"])
        )
    return (
        '  <section class="related-section">\n'
        "    <h2>前後のケーススタディ</h2>\n"
        '    <div class="related-nav-row">{}</div>\n'
        "  </section>\n"
    ).format(nav)


def assert_no_placeholders(html, label):
    left = sorted(set(re.findall(r"__[A-Z_]+__", html)))
    if left:
        raise BuildError("{}: 未置換のプレースホルダが残っています: {}".format(label, ", ".join(left)))


def render_case_study_page(cs, prev_cs, next_cs, template, code_css):
    body_html = render_markdown(cs["body_md"])
    n_fences = verify_fences(cs["body_md"], body_html)

    page_title = "設計ケーススタディ {}: {} - AIニュースまとめ".format(cs["no"], cs["title"])
    root = "../../"  # case-studies/<slug>/index.html → リポジトリルート

    html = template
    html = html.replace("__ADS_HEAD__", render_ads_head(cs["ads"]).rstrip("\n"))
    html = html.replace("__PAGE_TITLE__", esc(page_title))
    html = html.replace("__META_DESCRIPTION__", esc(build_description(cs, body_html)))
    html = html.replace("__CODE_CSS__", code_css)
    html = html.replace("__BACK_HREF__", "../")
    html = html.replace("__META_HTML__", render_meta_html(cs))
    html = html.replace("__BODY_HTML__", body_html)
    html = html.replace("__ADS_BOTTOM__", render_ads_unit(cs["ads"]).rstrip("\n"))
    html = html.replace("__RELATED_HTML__", render_related_html(prev_cs, next_cs).rstrip("\n"))
    html = html.replace("__ROOT__", root)
    assert_no_placeholders(html, cs["slug"])
    return html, n_fences


def render_listing_page(entries, template):
    cards = []
    for e in entries:
        tags_html = "".join('<span class="case-tag">#{}</span>'.format(esc(t)) for t in e["tags"])
        cards.append(
            '    <a class="case-card" href="{slug}/">\n'
            '      <div class="case-card-top">'
            '<span class="case-no">No. {no:03d}</span>'
            '<span class="case-genre">{genre}</span>'
            '<span class="case-date">{date}</span>'
            "</div>\n"
            '      <div class="case-title">{title}</div>\n'
            '      <div class="case-tags">{tags}</div>\n'
            "    </a>\n".format(
                slug=esc(e["slug"]),
                no=e["no"],
                genre=esc(e["genre"]),
                date=esc(format_date_ja(e["date"])),
                title=esc(e["title"]),
                tags=tags_html,
            )
        )
    cards_html = "".join(cards) or '    <div class="empty-message">まだ記事がありません</div>\n'

    html = template
    html = html.replace("__ADS_HEAD__", render_ads_head(LISTING_ADS).rstrip("\n"))
    html = html.replace(
        "__META_DESCRIPTION__",
        esc("実務の設計課題を「問題→自分の回答→AIレビュー→再考」の順で記録する設計ケーススタディの一覧（{}本）。".format(len(entries))),
    )
    html = html.replace("__COUNT__", str(len(entries)))
    html = html.replace("__CARDS_HTML__", cards_html.rstrip("\n"))
    html = html.replace("__ROOT__", "../")
    assert_no_placeholders(html, "case-studies/index.html")
    return html


# ---------------------------------------------------------------------------
def main():
    if not CONTENT_DIR.exists():
        print("{} がありません".format(CONTENT_DIR))
        return 1

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    index_template = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
    code_css = "\n".join(
        "    " + line for line in HtmlFormatter(style="default").get_style_defs(".codehilite").splitlines()
    )

    md_files = sorted(p for p in CONTENT_DIR.glob("*.md") if not p.name.startswith("_"))
    studies = []
    errors = []
    for md_path in md_files:
        try:
            studies.append(load_case_study(md_path))
        except BuildError as e:
            errors.append("{}: {}".format(md_path.name, e))
    if errors:
        print("読み込みエラー:")
        for e in errors:
            print("  [NG] " + e)
        return 1

    nos = [s["no"] for s in studies]
    dup = sorted({n for n in nos if nos.count(n) > 1})
    if dup:
        print("[NG] 連番が重複しています: {}".format(dup))
        return 1

    studies.sort(key=lambda s: s["no"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    built = 0
    for i, cs in enumerate(studies):
        prev_cs = studies[i - 1] if i > 0 else None
        next_cs = studies[i + 1] if i + 1 < len(studies) else None
        try:
            html, n_fences = render_case_study_page(cs, prev_cs, next_cs, template, code_css)
        except BuildError as e:
            print("  [NG] {}: {}".format(cs["slug"], e))
            return 1
        out_dir = OUTPUT_DIR / cs["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        built += 1
        print("  [OK] {}/index.html  (ads={}, コードブロック {} 件)".format(out_dir, cs["ads"], n_fences))
        for w in cs["warnings"]:
            print("       [警告] " + w)

    # 一覧・マニフェストは新しい番号順
    entries = [
        {
            "no": s["no"],
            "slug": s["slug"],
            "title": s["title"],
            "genre": s["genre"],
            "date": s["date"],
            "xPostedAt": s["xPostedAt"],
            "tags": s["tags"],
            "ads": s["ads"],
            "href": "case-studies/{}/".format(s["slug"]),
        }
        for s in sorted(studies, key=lambda s: s["no"], reverse=True)
    ]
    (OUTPUT_DIR / "index.html").write_text(render_listing_page(entries, index_template), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  [OK] {}/index.html, {}".format(OUTPUT_DIR, MANIFEST_PATH))

    # ソースの無い生成ディレクトリは消さずに警告だけ出す（URL を壊さないため手動判断）
    known = {s["slug"] for s in studies}
    for d in sorted(p for p in OUTPUT_DIR.iterdir() if p.is_dir()):
        if d.name not in known:
            print("  [警告] ソース .md が無い生成ディレクトリ: {}".format(d))

    print("ケーススタディを {} 件ビルドしました".format(built))
    return 0


if __name__ == "__main__":
    sys.exit(main())
