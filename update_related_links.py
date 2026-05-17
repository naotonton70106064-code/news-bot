"""既存の記事HTMLファイルに内部リンクセクションを差し込む（または更新する）ワンショットスクリプト。

対象: articles/{category}/YYYY-MM-DD.html
- 既にマーカー付きで挿入済みの場合は内容を最新化（冪等）
- 未挿入の場合は CSS / HTML / JS を該当位置に挿入

マーカー:
  CSS:  /* === RELATED-LINKS-CSS-START === */ ... /* === RELATED-LINKS-CSS-END === */
  HTML: <!-- RELATED-LINKS-HTML-START --> ... <!-- RELATED-LINKS-HTML-END -->
  JS:   /* === RELATED-LINKS-JS-START === */ ... /* === RELATED-LINKS-JS-END === */
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

CATEGORY_DISPLAY_NAMES = {
    "it": "IT・テクノロジー",
    "japan_economy": "日本経済",
    "world_economy": "世界経済",
}
ALL_CATEGORIES = ["it", "japan_economy", "world_economy"]


def build_related_links(date_str, category):
    """記事ページの関連リンク情報を構築する（main.pyと同一ロジック）。"""
    articles_root = Path("articles")
    cat_dir = articles_root / category

    other_categories = []
    for other in ALL_CATEGORIES:
        if other == category:
            continue
        target = articles_root / other / f"{date_str}.html"
        if target.exists():
            other_categories.append({
                "key": other,
                "name": CATEGORY_DISPLAY_NAMES[other],
                "href": f"../{other}/{date_str}.html",
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
            if (cat_dir / f"{cand_str}.html").exists():
                prev_link = {"date": cand_str, "href": f"{cand_str}.html"}
                break
        for delta in range(1, 366):
            candidate = current_dt + timedelta(days=delta)
            cand_str = candidate.strftime("%Y-%m-%d")
            if (cat_dir / f"{cand_str}.html").exists():
                next_link = {"date": cand_str, "href": f"{cand_str}.html"}
                break

    weekly = None
    if current_dt is not None:
        iso_year, iso_week, _ = current_dt.isocalendar()
        week_id = f"{iso_year}-W{iso_week:02d}"
        weekly_file = cat_dir / f"weekly-{week_id}.html"
        if weekly_file.exists():
            weekly = {"id": week_id, "href": f"weekly-{week_id}.html"}

    return {
        "currentDate": date_str,
        "currentCategory": category,
        "otherCategories": other_categories,
        "prevDate": prev_link,
        "nextDate": next_link,
        "weekly": weekly,
    }

CSS_START = "/* === RELATED-LINKS-CSS-START === */"
CSS_END = "/* === RELATED-LINKS-CSS-END === */"
HTML_START = "<!-- RELATED-LINKS-HTML-START -->"
HTML_END = "<!-- RELATED-LINKS-HTML-END -->"
JS_START = "/* === RELATED-LINKS-JS-START === */"
JS_END = "/* === RELATED-LINKS-JS-END === */"

CSS_BLOCK = f"""{CSS_START}
    .related-section {{ max-width: 800px; margin: 1.5rem auto 0; background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1.25rem; }}
    .related-section h2 {{ font-size: 14px; font-weight: 600; color: #111; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee; }}
    .related-group {{ margin-bottom: 1rem; }}
    .related-group:last-child {{ margin-bottom: 0; }}
    .related-group-title {{ font-size: 11px; font-weight: 600; color: #888; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .related-links {{ display: flex; flex-direction: column; gap: 8px; }}
    .related-nav-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .related-link {{ display: inline-flex; align-items: center; min-height: 44px; padding: 10px 14px; background: #f8f9fa; border: 1px solid #e5e5e5; border-radius: 8px; color: #1a73e8; font-size: 13px; text-decoration: none; line-height: 1.4; flex: 1 1 auto; }}
    .related-link:hover {{ background: #f0f0f0; }}
    .related-link:active {{ background: #e8e8e8; }}
    .related-link-weekly {{ background: #EEEDFE; border-color: #d9d6f9; color: #3C3489; }}
    .related-link-weekly:hover {{ background: #e4e1fb; }}
    @media (max-width: 480px) {{
      .related-nav-row {{ flex-direction: column; }}
    }}
    {CSS_END}"""

HTML_BLOCK = f"""  {HTML_START}
  <div class="related-section" id="related-section" style="display:none;">
    <h2>関連リンク</h2>
    <div id="related-content"></div>
  </div>
  {HTML_END}"""


def build_js_block(related):
    related_json = json.dumps(related, ensure_ascii=False, indent=6)
    return f"""    {JS_START}
    const relatedLinks = {related_json};
    (function renderRelatedLinks() {{
      if (!relatedLinks || typeof relatedLinks !== "object") return;
      const groups = [];

      const others = relatedLinks.otherCategories || [];
      if (others.length > 0) {{
        const linksHTML = others
          .map(o => `<a class="related-link" href="${{o.href}}">同じ日の${{o.name}}を見る →</a>`)
          .join("");
        groups.push(`
          <div class="related-group">
            <div class="related-group-title">同じ日の他カテゴリ</div>
            <div class="related-links">${{linksHTML}}</div>
          </div>`);
      }}

      const prev = relatedLinks.prevDate;
      const next = relatedLinks.nextDate;
      if (prev || next) {{
        const navHTML = [
          prev ? `<a class="related-link" href="${{prev.href}}">← 前日の記事へ (${{prev.date}})</a>` : "",
          next ? `<a class="related-link" href="${{next.href}}">翌日の記事へ (${{next.date}}) →</a>` : "",
        ].filter(Boolean).join("");
        groups.push(`
          <div class="related-group">
            <div class="related-group-title">日付ナビ</div>
            <div class="related-nav-row">${{navHTML}}</div>
          </div>`);
      }}

      const weekly = relatedLinks.weekly;
      if (weekly && weekly.href) {{
        groups.push(`
          <div class="related-group">
            <div class="related-group-title">週次サマリー</div>
            <div class="related-links">
              <a class="related-link related-link-weekly" href="${{weekly.href}}">この週のまとめを見る (${{weekly.id}}) →</a>
            </div>
          </div>`);
      }}

      if (groups.length === 0) return;
      const section = document.getElementById("related-section");
      const content = document.getElementById("related-content");
      content.innerHTML = groups.join("");
      section.style.display = "block";
    }})();
    {JS_END}"""


def upsert_block(html, start_marker, end_marker, new_block, fallback_anchor, anchor_position="before"):
    """マーカー間を new_block で置換。マーカーが無ければ fallback_anchor の前/後に挿入。"""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    if pattern.search(html):
        return pattern.sub(lambda _: new_block, html)

    if fallback_anchor not in html:
        raise ValueError(f"アンカーが見つかりません: {fallback_anchor!r}")

    if anchor_position == "before":
        return html.replace(fallback_anchor, new_block + "\n" + fallback_anchor, 1)
    return html.replace(fallback_anchor, fallback_anchor + "\n" + new_block, 1)


def process_file(html_path: Path, category: str, date_str: str) -> bool:
    html = html_path.read_text(encoding="utf-8")
    original = html

    related = build_related_links(date_str, category)
    js_block = build_js_block(related)

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
        HTML_BLOCK,
        fallback_anchor='  <div class="footer-note">',
        anchor_position="before",
    )
    html = upsert_block(
        html,
        JS_START, JS_END,
        js_block,
        fallback_anchor="  </script>",
        anchor_position="before",
    )

    if html == original:
        return False

    html_path.write_text(html, encoding="utf-8")
    return True


def main():
    articles_root = Path("articles")
    pattern = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.html$")

    targets = []
    for cat_dir in articles_root.iterdir():
        if not cat_dir.is_dir():
            continue
        category = cat_dir.name
        for html_file in cat_dir.glob("*.html"):
            m = pattern.match(html_file.name)
            if not m:
                continue
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            targets.append((html_file, category, date_str))

    print(f"対象ファイル数: {len(targets)}")
    updated = 0
    skipped = 0
    for html_file, category, date_str in targets:
        try:
            changed = process_file(html_file, category, date_str)
            if changed:
                updated += 1
                print(f"  [OK] 更新: {html_file}")
            else:
                skipped += 1
        except Exception as e:
            print(f"  [NG] エラー: {html_file} - {e}")

    print(f"\n完了: 更新 {updated} / スキップ {skipped} / 合計 {len(targets)}")


if __name__ == "__main__":
    main()
