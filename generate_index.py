"""記事一覧ページ（index.html）を自動生成するスクリプト"""
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

CATEGORIES = {
    "it": "IT・テクノロジー",
    "japan_economy": "日本経済",
    "world_economy": "世界経済",
}


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
                "titles": [get_display_title(a) for a in articles[:3]],
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
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
            legacy_days.append({
                "date": date_str,
                "count": len(articles),
                "titles": [get_display_title(a) for a in articles[:3]],
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

    # JSON化
    categories_json = json.dumps(
        {cat_id: {"name": cat_name, "weeks": all_data.get(cat_id, []), "weeklies": all_weeklies.get(cat_id, [])}
         for cat_id, cat_name in CATEGORIES.items()},
        ensure_ascii=False
    )

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
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
</head>
<body>
  <div class="site-header">
    <h1>AIニュースまとめ</h1>
    <p>最新のIT・テクノロジー・経済ニュースをAIが毎日自動収集・要約</p>
  </div>

  <div class="category-tabs" id="category-tabs">
    <button class="tab-btn active" data-cat="it">IT・テクノロジー</button>
    <button class="tab-btn" data-cat="japan_economy">日本経済</button>
    <button class="tab-btn" data-cat="world_economy">世界経済</button>
  </div>

  <div class="layout">
    <aside class="sidebar">
      <h2>週次サマリー</h2>
      <div id="sidebar-content"></div>
    </aside>

    <main class="main">
      <div class="week-nav">
        <button class="week-btn" id="btn-prev" onclick="prevWeek()">&#9664; 前の週へ</button>
        <span class="week-label" id="week-label"></span>
        <button class="week-btn" id="btn-next" onclick="nextWeek()">次の週へ &#9654;</button>
      </div>
      <div id="articles-container"></div>
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
    const validCategories = ["it", "japan_economy", "world_economy"];
    const urlCat = new URLSearchParams(window.location.search).get("cat");
    const initialCategory = validCategories.indexOf(urlCat) >= 0 ? urlCat : "it";

    const categories = {categories_json};
    let currentCategory = initialCategory;
    let currentPage = 0;

    const weekdays = ["\\u65E5", "\\u6708", "\\u706B", "\\u6C34", "\\u6728", "\\u91D1", "\\u571F"];

    function getArticlePath(category, date) {{
      if (category === "it") {{
        // 旧構造チェック: articles/直下にあるかカテゴリフォルダか
        const catData = categories[category];
        const weeks = catData.weeks;
        for (const w of weeks) {{
          for (const d of w.days) {{
            if (d.date === date) {{
              // 新構造のファイルがあればカテゴリパス、なければ旧パス
              return "articles/it/" + date + ".html";
            }}
          }}
        }}
      }}
      return "articles/" + category + "/" + date + ".html";
    }}

    function renderSidebar() {{
      const container = document.getElementById("sidebar-content");
      const weeklies = categories[currentCategory].weeklies || [];
      if (weeklies.length === 0) {{
        container.innerHTML = '<div class="sidebar-empty">まだありません</div>';
        return;
      }}
      container.innerHTML = weeklies.map(w =>
        '<a href="articles/' + w.filename + '" class="sidebar-link">' + w.id + '</a>'
      ).join("");
    }}

    function renderWeek() {{
      const catData = categories[currentCategory];
      const weeks = catData.weeks;
      const container = document.getElementById("articles-container");

      if (!weeks || weeks.length === 0) {{
        document.getElementById("week-label").textContent = catData.name;
        document.getElementById("btn-prev").disabled = true;
        document.getElementById("btn-next").disabled = true;
        container.innerHTML = '<div class="empty-message">\\u307E\\u3060\\u8A18\\u4E8B\\u304C\\u3042\\u308A\\u307E\\u305B\\u3093</div>';
        return;
      }}

      if (currentPage >= weeks.length) currentPage = weeks.length - 1;
      if (currentPage < 0) currentPage = 0;

      const week = weeks[currentPage];
      document.getElementById("week-label").textContent = week.label;
      document.getElementById("btn-prev").disabled = (currentPage >= weeks.length - 1);
      document.getElementById("btn-next").disabled = (currentPage <= 0);

      container.innerHTML = "";

      week.days.forEach(day => {{
        const dt = new Date(day.date + "T00:00:00");
        const wd = weekdays[dt.getDay()];
        const display = dt.getFullYear() + "\\u5E74" + (dt.getMonth()+1) + "\\u6708" + dt.getDate() + "\\u65E5";

        let titlesHtml = day.titles.map(t => "<li>\\u30FB" + t + "</li>").join("");
        if (day.count > 3) {{
          titlesHtml += '<li class="more">...\\u4ED6' + (day.count - 3) + '\\u4EF6</li>';
        }}

        const card = document.createElement("a");
        card.href = getArticlePath(currentCategory, day.date);
        card.className = "day-card";
        card.innerHTML = '<div class="day-date">' + display + '\\uFF08' + wd + '\\uFF09</div>'
          + '<div class="day-count">' + day.count + '\\u4EF6\\u306E\\u8A18\\u4E8B</div>'
          + '<ul class="day-titles">' + titlesHtml + '</ul>';
        container.appendChild(card);
      }});
    }}

    function switchCategory(cat) {{
      currentCategory = cat;
      currentPage = 0;
      document.querySelectorAll(".tab-btn").forEach(btn => {{
        btn.classList.toggle("active", btn.dataset.cat === cat);
      }});
      renderSidebar();
      renderWeek();
    }}

    function prevWeek() {{
      const weeks = categories[currentCategory].weeks;
      if (currentPage < weeks.length - 1) {{
        currentPage++;
        renderWeek();
      }}
    }}

    function nextWeek() {{
      if (currentPage > 0) {{
        currentPage--;
        renderWeek();
      }}
    }}

    // タブクリックイベント
    document.querySelectorAll(".tab-btn").forEach(btn => {{
      btn.addEventListener("click", () => switchCategory(btn.dataset.cat));
    }});

    // 初期タブの見た目を初期カテゴリに合わせる
    document.querySelectorAll(".tab-btn").forEach(btn => {{
      btn.classList.toggle("active", btn.dataset.cat === currentCategory);
    }});

    // 初期表示
    renderSidebar();
    renderWeek();
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
