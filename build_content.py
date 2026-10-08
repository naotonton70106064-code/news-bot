"""手書き Markdown コンテンツ（設計ケーススタディ / 管理人ブログ）を静的 HTML にビルドするスクリプト。

ニュース記事（RSS → JSON → render.py）とは別系統。ローカルで実行して生成物をコミットする
（CI は実行しない。CI の generate_index.py は一覧ページの存在だけを見てサイドバーにリンクを出す）。

コレクション（COLLECTIONS で定義）:
  case-studies: content/case-studies/NNN-slug.md → case-studies/NNN-slug/index.html（連番あり、ads 省略時 true）
  blog:         content/blog/slug.md             → blog/slug/index.html          （連番なし、ads 省略時 false）
各コレクションで一覧 {out}/index.html とマニフェスト {out}/index.json も生成する。

frontmatter（YAML）:
  共通: title, date, tags[]（任意）, ads（任意: AdSense コードを出すか）, description（任意）
  case-studies のみ: no（通し番号 = ファイル名の3桁連番と一致必須）, genre

依存（ローカルのみ）: pip install markdown pygments pyyaml
実行: python build_content.py            # 全コレクション
      python build_content.py blog       # 指定コレクションのみ
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

TEMPLATES_DIR = Path("templates")

COLLECTIONS = {
    "case-studies": {
        "name": "設計ケーススタディ",
        "src": Path("content") / "case-studies",
        "out": Path("case-studies"),
        # ファイル名: 3桁連番-slug.md。連番は frontmatter no / 本文 h1 と一致必須
        "filename_re": re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$"),
        "numbered": True,
        "h1_re": re.compile(r"^#\s+設計ケーススタディ\s*(\d+)\s*[:：]\s*(.+?)\s*$", re.MULTILINE),
        "required_keys": ("title", "genre", "date"),
        "required_h2": (
            "Problem", "Question", "自分の回答", "なぜそう考えたか",
            "AIレビュー", "再考・気づき", "設計ポイント",
        ),
        "ads_default": True,
        "listing_ads": True,  # 一覧は他の一覧系ページと同じく head ローダのみ
        "detail_template": "post.html",
        "index_template": "case_studies_index.html",
        "back_label": "ケーススタディ一覧に戻る",
        "footer_note": "本記事は筆者の設計判断と AI レビューの記録であり、特定環境での正しさを保証するものではありません。",
        "title_suffix": " - AIニュースまとめ",
        "listing_description": "実務の設計課題を「問題→自分の回答→AIレビュー→再考」の順で記録する設計ケーススタディの一覧（{count}本）。",
    },
    "blog": {
        "name": "管理人ブログ",
        "src": Path("content") / "blog",
        "out": Path("blog"),
        # ファイル名: slug.md（半角英数字とハイフン）。並び順は date
        "filename_re": re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)\.md$"),
        "numbered": False,
        "h1_re": re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE),
        "required_keys": ("title", "date"),
        "required_h2": (),
        "ads_default": False,  # ブログは AdSense を一切出さない
        "listing_ads": False,
        "detail_template": "post.html",
        "index_template": "blog_index.html",
        "back_label": "ブログ一覧に戻る",
        "footer_note": "本記事には商品・サービスのアフィリエイトリンクを含む場合があります。",
        "title_suffix": " - 管理人ブログ | AIニュースまとめ",
        "listing_description": "AIニュースまとめ管理人のブログ。サイト運営やツールの記録（{count}本）。",
    },
}

FENCE_RE = re.compile(r"^(`{3,}|~{3,})[^\n]*\n(.*?)\n\1[ \t]*$", re.MULTILINE | re.DOTALL)

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


def load_post(md_path, col):
    """1 記事を読み込んで検証し、正規化した dict を返す"""
    m = col["filename_re"].match(md_path.name)
    if not m:
        if col["numbered"]:
            raise BuildError("ファイル名は NNN-slug.md（3桁連番 + 半角英数字とハイフン）にしてください")
        raise BuildError("ファイル名は slug.md（半角英小文字・数字・ハイフン）にしてください")
    slug = md_path.stem  # URL のディレクトリ名

    text = md_path.read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)

    required = list(col["required_keys"]) + (["no"] if col["numbered"] else [])
    missing = [k for k in required if k not in meta]
    if missing:
        raise BuildError("frontmatter に必須キーがありません: {}".format(", ".join(missing)))

    ads = meta.get("ads", col["ads_default"])
    if not isinstance(ads, bool):
        raise BuildError("ads は true / false で指定してください: {!r}".format(ads))

    h1 = col["h1_re"].search(body)
    if not h1:
        if col["numbered"]:
            raise BuildError("本文の h1 は「# 設計ケーススタディ NN: タイトル」の形式にしてください")
        raise BuildError("本文に h1（# タイトル）がありません")

    no = None
    if col["numbered"]:
        file_no = int(m.group(1))
        if not isinstance(meta["no"], int):
            raise BuildError("no は整数で指定してください: {!r}".format(meta["no"]))
        if meta["no"] != file_no:
            raise BuildError("frontmatter の no ({}) とファイル名の連番 ({}) が一致しません".format(meta["no"], file_no))
        if int(h1.group(1)) != file_no:
            raise BuildError("h1 の番号 ({}) とファイル名の連番 ({}) が一致しません".format(h1.group(1), file_no))
        no = file_no

    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        raise BuildError("tags はリストで指定してください: {!r}".format(tags))

    h2s = re.findall(r"^##\s+(.+?)\s*$", body, re.MULTILINE)
    warnings = []
    for req in col["required_h2"]:
        if not any(h.startswith(req) for h in h2s):
            warnings.append("必須見出し「## {}」がありません".format(req))

    return {
        "slug": slug,
        "no": no,
        "title": str(meta["title"]).strip(),
        "genre": str(meta.get("genre", "")).strip(),
        "date": _to_iso_date(meta["date"], "date"),
        "xPostedAt": _to_iso_datetime_or_none(meta.get("xPostedAt"), "xPostedAt"),
        "tags": [str(t).strip() for t in tags],
        "ads": ads,
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


def page_heading(post, col):
    if col["numbered"]:
        return "設計ケーススタディ {}: {}".format(post["no"], post["title"])
    return post["title"]


def build_description(post, col, body_html):
    if post["description"]:
        return post["description"][:160]
    text = re.sub(r"<pre>.*?</pre>", " ", body_html, flags=re.DOTALL)
    text = re.sub(r"<h1[^>]*>.*?</h1>", " ", text, flags=re.DOTALL)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return (page_heading(post, col) + "。" + text)[:160]


def format_date_ja(iso):
    y, m, d = iso.split("-")
    return "{}年{}月{}日".format(int(y), int(m), int(d))


def render_meta_html(post):
    parts = []
    if post["no"] is not None:
        parts.append('      <span class="case-no">No. {:03d}</span>'.format(post["no"]))
    if post["genre"]:
        parts.append('      <span class="case-genre">{}</span>'.format(esc(post["genre"])))
    parts.append('      <span class="case-date">{}</span>'.format(esc(format_date_ja(post["date"]))))
    for t in post["tags"]:
        parts.append('      <span class="case-tag">#{}</span>'.format(esc(t)))
    if post["xPostedAt"]:
        parts.append('      <span class="case-x">X 投稿: {}</span>'.format(esc(post["xPostedAt"][:10])))
    return "\n".join(parts)


def _nav_label(post):
    if post["no"] is not None:
        return "No. {:03d} {}".format(post["no"], esc(post["title"]))
    return esc(post["title"])


def render_related_html(prev_post, next_post, heading):
    if not prev_post and not next_post:
        return ""
    nav = ""
    if prev_post:
        nav += '<a class="related-link" href="../{}/">&larr; {}</a>'.format(esc(prev_post["slug"]), _nav_label(prev_post))
    if next_post:
        nav += '<a class="related-link" href="../{}/">{} &rarr;</a>'.format(esc(next_post["slug"]), _nav_label(next_post))
    return (
        '  <section class="related-section">\n'
        "    <h2>{}</h2>\n"
        '    <div class="related-nav-row">{}</div>\n'
        "  </section>\n"
    ).format(esc(heading), nav)


def assert_no_placeholders(html, label):
    left = sorted(set(re.findall(r"__[A-Z_]+__", html)))
    if left:
        raise BuildError("{}: 未置換のプレースホルダが残っています: {}".format(label, ", ".join(left)))


def render_post_page(post, col, prev_post, next_post, template, code_css):
    body_html = render_markdown(post["body_md"])
    n_fences = verify_fences(post["body_md"], body_html)

    page_title = page_heading(post, col) + col["title_suffix"]
    related_heading = "前後のケーススタディ" if col["numbered"] else "前後の記事"

    html = template
    html = html.replace("__ADS_HEAD__", render_ads_head(post["ads"]).rstrip("\n"))
    html = html.replace("__PAGE_TITLE__", esc(page_title))
    html = html.replace("__META_DESCRIPTION__", esc(build_description(post, col, body_html)))
    html = html.replace("__CODE_CSS__", code_css)
    html = html.replace("__BACK_HREF__", "../")
    html = html.replace("__BACK_LABEL__", esc(col["back_label"]))
    html = html.replace("__META_HTML__", render_meta_html(post))
    html = html.replace("__BODY_HTML__", body_html)
    html = html.replace("__ADS_BOTTOM__", render_ads_unit(post["ads"]).rstrip("\n"))
    html = html.replace("__RELATED_HTML__", render_related_html(prev_post, next_post, related_heading).rstrip("\n"))
    html = html.replace("__FOOTER_NOTE__", esc(col["footer_note"]))
    html = html.replace("__ROOT__", "../../")  # {out}/<slug>/index.html → リポジトリルート
    assert_no_placeholders(html, "{}/{}".format(col["out"], post["slug"]))
    return html, n_fences


def render_listing_page(entries, col, template):
    cards = []
    for e in entries:
        tags_html = "".join('<span class="case-tag">#{}</span>'.format(esc(t)) for t in e["tags"])
        badges = ""
        if e.get("no") is not None:
            badges += '<span class="case-no">No. {:03d}</span>'.format(e["no"])
        if e.get("genre"):
            badges += '<span class="case-genre">{}</span>'.format(esc(e["genre"]))
        desc_html = ""
        if e.get("description"):
            desc_html = '      <div class="case-desc">{}</div>\n'.format(esc(e["description"]))
        cards.append(
            '    <a class="case-card" href="{slug}/">\n'
            '      <div class="case-card-top">{badges}<span class="case-date">{date}</span></div>\n'
            '      <div class="case-title">{title}</div>\n'
            "{desc}"
            '      <div class="case-tags">{tags}</div>\n'
            "    </a>\n".format(
                slug=esc(e["slug"]),
                badges=badges,
                date=esc(format_date_ja(e["date"])),
                title=esc(e["title"]),
                desc=desc_html,
                tags=tags_html,
            )
        )
    cards_html = "".join(cards) or '    <div class="empty-message">まだ記事がありません</div>\n'

    html = template
    html = html.replace("__ADS_HEAD__", render_ads_head(col["listing_ads"]).rstrip("\n"))
    html = html.replace("__META_DESCRIPTION__", esc(col["listing_description"].format(count=len(entries))))
    html = html.replace("__COUNT__", str(len(entries)))
    html = html.replace("__CARDS_HTML__", cards_html.rstrip("\n"))
    html = html.replace("__ROOT__", "../")
    assert_no_placeholders(html, "{}/index.html".format(col["out"]))
    return html


# ---------------------------------------------------------------------------
def build_collection(key, code_css):
    col = COLLECTIONS[key]
    src, out = col["src"], col["out"]
    print("[{}] {} → {}".format(key, src, out))
    if not src.exists():
        print("  [NG] {} がありません".format(src))
        return False

    template = (TEMPLATES_DIR / col["detail_template"]).read_text(encoding="utf-8")
    index_template = (TEMPLATES_DIR / col["index_template"]).read_text(encoding="utf-8")

    md_files = sorted(p for p in src.glob("*.md") if not p.name.startswith("_"))
    posts = []
    errors = []
    for md_path in md_files:
        try:
            posts.append(load_post(md_path, col))
        except BuildError as e:
            errors.append("{}: {}".format(md_path.name, e))
    if errors:
        print("  読み込みエラー:")
        for e in errors:
            print("    [NG] " + e)
        return False

    if col["numbered"]:
        nos = [p["no"] for p in posts]
        dup = sorted({n for n in nos if nos.count(n) > 1})
        if dup:
            print("  [NG] 連番が重複しています: {}".format(dup))
            return False
        posts.sort(key=lambda p: p["no"])  # 前後ナビは番号順
    else:
        posts.sort(key=lambda p: (p["date"], p["slug"]))  # 前後ナビは日付順

    out.mkdir(parents=True, exist_ok=True)
    for i, post in enumerate(posts):
        prev_post = posts[i - 1] if i > 0 else None
        next_post = posts[i + 1] if i + 1 < len(posts) else None
        try:
            html, n_fences = render_post_page(post, col, prev_post, next_post, template, code_css)
        except BuildError as e:
            print("  [NG] {}: {}".format(post["slug"], e))
            return False
        out_dir = out / post["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        print("  [OK] {}/index.html  (ads={}, コードブロック {} 件)".format(out_dir.as_posix(), post["ads"], n_fences))
        for w in post["warnings"]:
            print("       [警告] " + w)

    # 一覧・マニフェストは新しい順
    if col["numbered"]:
        ordered = sorted(posts, key=lambda p: p["no"], reverse=True)
    else:
        ordered = sorted(posts, key=lambda p: (p["date"], p["slug"]), reverse=True)
    entries = []
    for p in ordered:
        e = {
            "slug": p["slug"],
            "title": p["title"],
            "date": p["date"],
            "tags": p["tags"],
            "ads": p["ads"],
            "description": p["description"],
            "href": "{}/{}/".format(out.as_posix(), p["slug"]),
        }
        if col["numbered"]:
            e["no"] = p["no"]
            e["genre"] = p["genre"]
            e["xPostedAt"] = p["xPostedAt"]
        entries.append(e)

    (out / "index.html").write_text(render_listing_page(entries, col, index_template), encoding="utf-8")
    (out / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  [OK] {}/index.html, {}/index.json".format(out.as_posix(), out.as_posix()))

    # ソースの無い生成ディレクトリは消さずに警告だけ出す（URL を壊さないため手動判断）
    known = {p["slug"] for p in posts}
    for d in sorted(p for p in out.iterdir() if p.is_dir()):
        if d.name not in known:
            print("  [警告] ソース .md が無い生成ディレクトリ: {}".format(d.as_posix()))

    print("  {} 件ビルドしました".format(len(posts)))
    return True


def main(argv):
    keys = argv[1:] or list(COLLECTIONS)
    unknown = [k for k in keys if k not in COLLECTIONS]
    if unknown:
        print("不明なコレクション: {}（有効: {}）".format(", ".join(unknown), ", ".join(COLLECTIONS)))
        return 1

    code_css = "\n".join(
        "    " + line for line in HtmlFormatter(style="default").get_style_defs(".codehilite").splitlines()
    )
    ok = True
    for key in keys:
        ok = build_collection(key, code_css) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
