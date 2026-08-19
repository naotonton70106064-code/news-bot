"""既存の記事HTMLにサイト共通フッターリンク（プライバシーポリシー等）を差し込むワンショットスクリプト。

対象:
- articles/{category}/*.html（日次・週次）… リンクは ../../ 起点
- articles/*.html（旧構造のIT記事）… リンクは ../ 起点

既にマーカー付きで挿入済みの場合は内容を最新化（冪等）。
新規生成分は templates/dashboard.html / weekly.py のテンプレート側に同じブロックが入っているため、
このスクリプトはバックフィル専用。

マーカー:
  CSS:  /* === SITE-FOOTER-CSS-START === */ ... /* === SITE-FOOTER-CSS-END === */
  HTML: <!-- SITE-FOOTER-HTML-START --> ... <!-- SITE-FOOTER-HTML-END -->
"""
import re
from pathlib import Path

CSS_START = "/* === SITE-FOOTER-CSS-START === */"
CSS_END = "/* === SITE-FOOTER-CSS-END === */"
HTML_START = "<!-- SITE-FOOTER-HTML-START -->"
HTML_END = "<!-- SITE-FOOTER-HTML-END -->"

CSS_BLOCK = f"""    {CSS_START}
    .site-footer-links {{ max-width: 800px; margin: 1.5rem auto 0; padding-top: 1rem; border-top: 1px solid #e5e5e5; text-align: center; }}
    .site-footer-links a {{ font-size: 12px; color: #1a73e8; text-decoration: none; margin: 0 10px; }}
    .site-footer-links a:hover {{ text-decoration: underline; }}
    {CSS_END}"""


def build_html_block(prefix: str) -> str:
    return f"""  {HTML_START}
  <div class="site-footer-links">
    <a href="{prefix}privacy.html">プライバシーポリシー</a>
    <a href="{prefix}about.html">運営者情報</a>
    <a href="{prefix}contact.html">お問い合わせ</a>
  </div>
  {HTML_END}"""


def upsert_block(html, start_marker, end_marker, new_block, fallback_anchor, anchor_position="before"):
    """マーカー間を new_block で置換。マーカーが無ければ fallback_anchor の前/後に挿入。"""
    # マーカー前のインデントも含めて置換し、再実行時にインデントが増殖しないようにする
    pattern = re.compile(
        r"[ \t]*" + re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    if pattern.search(html):
        return pattern.sub(lambda _: new_block, html)

    if fallback_anchor not in html:
        raise ValueError(f"アンカーが見つかりません: {fallback_anchor!r}")

    if anchor_position == "before":
        return html.replace(fallback_anchor, new_block + "\n" + fallback_anchor, 1)
    return html.replace(fallback_anchor, fallback_anchor + "\n" + new_block, 1)


def process_file(html_path: Path, prefix: str) -> bool:
    html = html_path.read_text(encoding="utf-8")
    original = html

    html = upsert_block(
        html,
        CSS_START, CSS_END,
        CSS_BLOCK,
        fallback_anchor="  </style>",
        anchor_position="before",
    )
    html = upsert_block(
        html,
        HTML_START, HTML_END,
        build_html_block(prefix),
        fallback_anchor="</body>",
        anchor_position="before",
    )

    if html == original:
        return False

    html_path.write_text(html, encoding="utf-8")
    return True


def main():
    articles_root = Path("articles")

    targets = []
    # 現行構造: articles/{category}/*.html
    for cat_dir in sorted(articles_root.iterdir()):
        if not cat_dir.is_dir():
            continue
        for html_file in sorted(cat_dir.glob("*.html")):
            targets.append((html_file, "../../"))
    # 旧構造: articles/*.html
    for html_file in sorted(articles_root.glob("*.html")):
        targets.append((html_file, "../"))

    print(f"対象ファイル数: {len(targets)}")
    updated = 0
    skipped = 0
    for html_file, prefix in targets:
        try:
            changed = process_file(html_file, prefix)
            if changed:
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  [NG] エラー: {html_file} - {e}")

    print(f"完了: 更新 {updated} / スキップ {skipped} / 合計 {len(targets)}")


if __name__ == "__main__":
    main()
