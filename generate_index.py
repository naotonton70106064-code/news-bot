"""記事一覧ページ（index.html）を自動生成するスクリプト。

記事タイトル一覧は生成時に <body> 内の HTML として直接書き出す。
JS はカテゴリタブ切り替えと週送りのために既存 DOM の表示/非表示を
切り替えるだけで、JS が動かなくても内容が HTML ソースに存在する。
"""
import html as _html
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

CATEGORIES = {
    "it": "IT・テクノロジー",
    "japan_economy": "日本経済",
    "world_economy": "世界経済",
}

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def esc(text):
    if text is None:
        return ""
    return _html.escape(str(text), quote=True)


def _is_valid_title(t):
    """タイトルとして有効か（空・記号のみは無効）"""
    if not t:
        return False
    s = t.strip()
    if not s:
        return False
    return not re.fullmatch(r"[-—ー―ｰ_=・\s]+", s)


def get_display_title(article):
    """日本語タイトルを返す。空・無効な場合はoriginal titleにフォールバック。
    レガシー構造（summaryフィールド）があれば3行要約1行目を優先抽出する。"""
    jt = article.get("japanese_title")
    if _is_valid_title(jt):
        return jt
    summary = article.get("summary", "")
    if summary:
        for line in summary.split("\n"):
            line = line.strip()
            m = re.match(r"^[1１][\.\．、]\s*(.+)$", line)
            if m:
                return m.group(1).strip()
    return article.get("title", "")


def get_week_start(dt):
    """日曜始まりの週の開始日（日曜日）を返す"""
    days_since_sunday = (dt.weekday() + 1) % 7
    return dt - timedelta(days=days_since_sunday)


def load_category_data(category):
    """カテゴリのJSON記事を全て読み込む"""
    articles_dir = Path("articles") / category
    if not articles_dir.exists():
        return [], []

    json_files = sorted(articles_dir.glob("*.json"), reverse=True)

    days = []
    for json_file in json_files:
        date_str = json_file.stem
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
            days.append({
                "date": date_str,
                "count": len(articles),
                "titles": [get_display_title(a) for a in articles],
                "href": f"articles/{category}/{date_str}.html",
            })
        except (json.JSONDecodeError, KeyError):
            continue

    weekly_files = sorted(articles_dir.glob("weekly-*.html"), reverse=True)
    weeklies = []
    for wf in weekly_files:
        week_id = wf.stem.replace("weekly-", "")
        weeklies.append({"id": week_id, "filename": f"{category}/{wf.name}"})

    return days, weeklies


def group_by_weeks(days):
    """日付データを週ごとにグループ化"""
    weeks = {}
    for day in days:
        dt = datetime.strptime(day["date"], "%Y-%m-%d")
        week_sunday = get_week_start(dt)
        week_key = week_sunday.strftime("%Y-%m-%d")
        weeks.setdefault(week_key, []).append(day)

    sorted_weeks = sorted(weeks.keys(), reverse=True)
    weeks_data = []
    for week_key in sorted_weeks:
        week_days = sorted(weeks[week_key], key=lambda d: d["date"], reverse=True)
        sunday = datetime.strptime(week_key, "%Y-%m-%d")
        saturday = sunday + timedelta(days=6)
        label = f"{sunday.strftime('%Y年%m/%d')}〜{saturday.strftime('%m/%d')}"
        weeks_data.append({
            "key": week_key,
            "label": label,
            "days": week_days,
        })

    return weeks_data


def render_day_card(day):
    """1日分のカード HTML（日付・件数・記事タイトル一覧）"""
    dt = datetime.strptime(day["date"], "%Y-%m-%d")
    display = f"{dt.year}年{dt.month}月{dt.day}日（{WEEKDAYS_JA[dt.weekday()]}）"
    titles_html = "".join(
        f"<li>・{esc(t)}</li>" for t in day["titles"] if str(t).strip()
    )
    return (
        f'        <a class="day-card" href="{esc(day["href"])}">\n'
        f'          <h3 class="day-date">{esc(display)}</h3>\n'
        f'          <div class="day-count">{day["count"]}件の記事</div>\n'
        f'          <ul class="day-titles">{titles_html}</ul>\n'
        f"        </a>\n"
    )


def render_panels(all_data, initial_category):
    """全カテゴリ・全週分のパネル HTML を返す"""
    parts = []
    for cat_id, cat_name in CATEGORIES.items():
        weeks = all_data.get(cat_id) or []
        if not weeks:
            hidden = "" if cat_id == initial_category else " hidden"
            parts.append(
                f'      <section class="week-panel" data-cat="{cat_id}" data-page="0"'
                f' data-label="{esc(cat_name)}"{hidden}>\n'
                f'        <h2 class="week-heading">{esc(cat_name)}</h2>\n'
                f'        <div class="empty-message">まだ記事がありません</div>\n'
                f"      </section>\n"
            )
            continue
        for page, week in enumerate(weeks):
            hidden = "" if (cat_id == initial_category and page == 0) else " hidden"
            cards = "".join(render_day_card(d) for d in week["days"])
            parts.append(
                f'      <section class="week-panel" data-cat="{cat_id}" data-page="{page}"'
                f' data-label="{esc(week["label"])}"{hidden}>\n'
                f'        <h2 class="week-heading">{esc(cat_name)} {esc(week["label"])}</h2>\n'
                f"{cards}"
                f"      </section>\n"
            )
    return "".join(parts)


def render_sidebar(all_weeklies, initial_category):
    """週次サマリーリンクを全カテゴリ分書き出す"""
    parts = []
    for cat_id, cat_name in CATEGORIES.items():
        weeklies = all_weeklies.get(cat_id) or []
        hidden = "" if cat_id == initial_category else " hidden"
        if weeklies:
            links = "".join(
                f'<a href="articles/{esc(w["filename"])}" class="sidebar-link">{esc(w["id"])}</a>'
                for w in weeklies
            )
        else:
            links = '<div class="sidebar-empty">まだありません</div>'
        parts.append(
            f'        <div class="sidebar-cat" data-cat="{cat_id}"{hidden}>'
            f'<div class="sidebar-cat-name">{esc(cat_name)}</div>{links}</div>\n'
        )
    return "".join(parts)


def generate_index():
    # 全カテゴリのデータ収集
    all_data = {}
    all_weeklies = {}
    for cat_id, cat_name in CATEGORIES.items():
        days, weeklies = load_category_data(cat_id)
        all_data[cat_id] = group_by_weeks(days)
        all_weeklies[cat_id] = weeklies

    # 旧構造（articles/直下）のデータもIT扱いで読み込む
    legacy_dir = Path("articles")
    legacy_jsons = sorted(legacy_dir.glob("*.json"), reverse=True)
    legacy_days = []
    for json_file in legacy_jsons:
        date_str = json_file.stem
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
            legacy_days.append({
                "date": date_str,
                "count": len(articles),
                "titles": [get_display_title(a) for a in articles],
                # 旧構造の記事ページは articles/ 直下にある（articles/it/ には無い）
                "href": f"articles/{date_str}.html",
            })
        except (json.JSONDecodeError, KeyError):
            continue

    legacy_weeklies_files = sorted(legacy_dir.glob("weekly-*.html"), reverse=True)
    legacy_weeklies = []
    for wf in legacy_weeklies_files:
        week_id = wf.stem.replace("weekly-", "")
        legacy_weeklies.append({"id": week_id, "filename": wf.name})

    if legacy_days:
        legacy_weeks = group_by_weeks(legacy_days)
        # 新構造のITデータと統合（同一週は日単位でマージし、同日付は新構造を優先）
        existing_weeks_map = {w["key"]: w for w in all_data.get("it", [])}
        for w in legacy_weeks:
            if w["key"] in existing_weeks_map:
                existing = existing_weeks_map[w["key"]]
                existing_dates = {d["date"] for d in existing["days"]}
                for d in w["days"]:
                    if d["date"] not in existing_dates:
                        existing["days"].append(d)
                existing["days"] = sorted(existing["days"], key=lambda d: d["date"], reverse=True)
            else:
                all_data.setdefault("it", []).append(w)
        all_data["it"] = sorted(all_data.get("it", []), key=lambda w: w["key"], reverse=True)

        existing_weekly_ids = {w["id"] for w in all_weeklies.get("it", [])}
        for w in legacy_weeklies:
            if w["id"] not in existing_weekly_ids:
                all_weeklies.setdefault("it", []).append(w)

    initial_category = "it"
    initial_weeks = all_data.get(initial_category) or []
    initial_label = initial_weeks[0]["label"] if initial_weeks else CATEGORIES[initial_category]
    prev_disabled = " disabled" if len(initial_weeks) <= 1 else ""
    next_disabled = " disabled"  # 初期表示は最新週なので「次の週へ」は無効

    panels_html = render_panels(all_data, initial_category)
    sidebar_html = render_sidebar(all_weeklies, initial_category)

    tabs_html = "".join(
        f'    <button class="tab-btn{" active" if cat_id == initial_category else ""}"'
        f' data-cat="{cat_id}" type="button">{esc(cat_name)}</button>\n'
        for cat_id, cat_name in CATEGORIES.items()
    )

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <!-- ADSENSE-START -->
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1944739806788973"
     crossorigin="anonymous"></script>
  <!-- ADSENSE-END -->
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIニュースまとめ - 毎日のIT・テクノロジーニュースをAIが要約</title>
  <meta name="description" content="最新のIT・テクノロジー・経済ニュースをAIが毎日自動収集・要約。背景解説や今後の予測まで、忙しいあなたのためのニュースダイジェスト。">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8f9fa; color: #111; }}
    .site-header {{ padding: 2rem 1rem 0; text-align: center; background: #fff; }}
    .site-header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 6px; }}
    .site-header p {{ font-size: 14px; color: #666; margin-bottom: 1rem; }}
    .category-tabs {{ display: flex; justify-content: center; gap: 0; border-bottom: 1px solid #e5e5e5; background: #fff; padding: 0 1rem; }}
    .tab-btn {{ padding: 12px 24px; font-size: 14px; font-weight: 500; color: #666; background: none; border: none; border-bottom: 3px solid transparent; cursor: pointer; transition: all 0.2s; }}
    .tab-btn:hover {{ color: #111; }}
    .tab-btn.active {{ color: #111; border-bottom-color: #111; font-weight: 600; }}
    .layout {{ display: flex; max-width: 1100px; margin: 0 auto; min-height: calc(100vh - 250px); }}
    .sidebar {{ width: 220px; padding: 1.5rem 1rem; border-right: 1px solid #e5e5e5; background: #fff; flex-shrink: 0; }}
    .sidebar h2 {{ font-size: 14px; font-weight: 600; color: #555; margin-bottom: 12px; }}
    .sidebar-cat[hidden] {{ display: none; }}
    .sidebar-cat-name {{ display: none; font-size: 12px; font-weight: 600; color: #888; margin: 8px 0 4px; }}
    .sidebar-link {{ display: block; padding: 8px 12px; font-size: 13px; color: #1a73e8; text-decoration: none; border-radius: 6px; margin-bottom: 4px; }}
    .sidebar-link:hover {{ background: #f0f4ff; }}
    .sidebar-empty {{ font-size: 12px; color: #999; padding: 8px 12px; }}
    .main {{ flex: 1; padding: 1.5rem 2rem; }}
    .week-nav {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }}
    .week-label {{ font-size: 16px; font-weight: 600; }}
    .week-btn {{ padding: 8px 16px; font-size: 13px; background: #fff; border: 1px solid #ddd; border-radius: 8px; cursor: pointer; color: #333; }}
    .week-btn:hover {{ background: #f0f0f0; }}
    .week-btn:disabled {{ opacity: 0.3; cursor: default; }}
    .week-btn:disabled:hover {{ background: #fff; }}
    .week-panel[hidden] {{ display: none; }}
    .week-heading {{ display: none; font-size: 16px; font-weight: 600; margin: 1.5rem 0 0.75rem; }}
    .day-card {{ display: block; background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1.25rem; margin-bottom: 12px; text-decoration: none; color: inherit; transition: box-shadow 0.2s; }}
    .day-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .day-date {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
    .day-count {{ font-size: 12px; color: #888; margin-bottom: 8px; }}
    .day-titles {{ list-style: none; font-size: 13px; color: #444; line-height: 1.8; }}
    .day-titles .more {{ color: #888; }}
    .empty-message {{ text-align: center; padding: 3rem; color: #888; font-size: 14px; }}
    .footer {{ border-top: 1px solid #e5e5e5; padding: 2rem 1rem; text-align: center; background: #fff; }}
    .footer-links {{ margin-bottom: 8px; }}
    .footer-links a {{ font-size: 13px; color: #1a73e8; text-decoration: none; margin: 0 12px; }}
    .footer-links a:hover {{ text-decoration: underline; }}
    .footer-note {{ font-size: 11px; color: #aaa; }}
    @media (max-width: 768px) {{
      .layout {{ flex-direction: column; }}
      .sidebar {{ width: 100%; border-right: none; border-bottom: 1px solid #e5e5e5; padding: 1rem; }}
      .sidebar-link {{ display: inline-block; margin-right: 4px; }}
      .main {{ padding: 1rem; }}
      .tab-btn {{ padding: 10px 14px; font-size: 13px; }}
    }}
  </style>
  <noscript>
    <style>
      /* JS 無効時はタブ・週送りが使えないため、全カテゴリ・全週を並べて表示する */
      .week-panel[hidden], .sidebar-cat[hidden] {{ display: block !important; }}
      .week-heading, .sidebar-cat-name {{ display: block !important; }}
      .week-nav, .category-tabs {{ display: none !important; }}
    </style>
  </noscript>
</head>
<body>
  <div class="site-header">
    <h1>AIニュースまとめ</h1>
    <p>最新のIT・テクノロジー・経済ニュースをAIが毎日自動収集・要約</p>
  </div>

  <div class="category-tabs" id="category-tabs">
{tabs_html}  </div>

  <div class="layout">
    <aside class="sidebar">
      <h2>週次サマリー</h2>
      <div id="sidebar-content">
{sidebar_html}      </div>
    </aside>

    <main class="main">
      <div class="week-nav" id="week-nav">
        <button class="week-btn" id="btn-prev" type="button" onclick="prevWeek()"{prev_disabled}>&#9664; 前の週へ</button>
        <span class="week-label" id="week-label">{esc(initial_label)}</span>
        <button class="week-btn" id="btn-next" type="button" onclick="nextWeek()"{next_disabled}>次の週へ &#9654;</button>
      </div>
      <div id="articles-container">
{panels_html}      </div>
    </main>
  </div>

  <footer class="footer">
    <div class="footer-links">
      <a href="privacy.html">プライバシーポリシー</a>
      <a href="about.html">運営者情報</a>
      <a href="contact.html">お問い合わせ</a>
    </div>
    <div class="footer-note">本サイトの解釈・予測はAIによる見解であり、投資助言・専門的アドバイスではありません。</div>
  </footer>

  <script>
    // 記事タイトル一覧は生成時に HTML へ書き出し済み。
    // JS は既存 DOM の表示切り替え（カテゴリタブ・週送り）だけを担当する。
    (function () {{
      var validCategories = ["it", "japan_economy", "world_economy"];
      var panels = Array.prototype.slice.call(document.querySelectorAll(".week-panel"));
      var sidebarCats = Array.prototype.slice.call(document.querySelectorAll(".sidebar-cat"));
      var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab-btn"));
      var labelEl = document.getElementById("week-label");
      var prevBtn = document.getElementById("btn-prev");
      var nextBtn = document.getElementById("btn-next");

      var currentCategory = "{initial_category}";
      var currentPage = 0;

      function panelsOf(cat) {{
        return panels.filter(function (p) {{ return p.dataset.cat === cat; }});
      }}

      function render() {{
        var list = panelsOf(currentCategory);
        if (currentPage >= list.length) currentPage = list.length - 1;
        if (currentPage < 0) currentPage = 0;

        panels.forEach(function (p) {{
          p.hidden = !(p.dataset.cat === currentCategory && Number(p.dataset.page) === currentPage);
        }});
        sidebarCats.forEach(function (s) {{
          s.hidden = s.dataset.cat !== currentCategory;
        }});
        tabs.forEach(function (b) {{
          b.classList.toggle("active", b.dataset.cat === currentCategory);
        }});

        var active = list[currentPage];
        labelEl.textContent = active ? active.dataset.label : "";
        prevBtn.disabled = currentPage >= list.length - 1;
        nextBtn.disabled = currentPage <= 0;
      }}

      window.prevWeek = function () {{ currentPage++; render(); }};
      window.nextWeek = function () {{ currentPage--; render(); }};

      tabs.forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          currentCategory = btn.dataset.cat;
          currentPage = 0;
          render();
        }});
      }});

      var urlCat = new URLSearchParams(window.location.search).get("cat");
      if (validCategories.indexOf(urlCat) >= 0) {{
        currentCategory = urlCat;
      }}
      render();
    }})();
  </script>
</body>
</html>'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    total_days = sum(
        sum(len(w["days"]) for w in all_data.get(cat, []))
        for cat in CATEGORIES
    )
    print(f"index.html を生成しました（{total_days}日分、{len(CATEGORIES)}カテゴリ）")


if __name__ == "__main__":
    generate_index()
