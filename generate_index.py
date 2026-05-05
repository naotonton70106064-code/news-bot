"""記事一覧ページ（index.html）を自動生成するスクリプト"""
import json
from pathlib import Path
from datetime import datetime, timedelta


def get_week_start(dt):
    """日曜始まりの週の開始日（日曜日）を返す"""
    # weekday(): 月=0, 日=6 → 日曜始まりにするため調整
    days_since_sunday = (dt.weekday() + 1) % 7
    return dt - timedelta(days=days_since_sunday)


def generate_index():
    articles_dir = Path("articles")
    json_files = sorted(articles_dir.glob("*.json"), reverse=True)

    # 各日付の記事情報を収集
    days = []
    for json_file in json_files:
        date_str = json_file.stem  # e.g. "2026-05-03"
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
            days.append({
                "date": date_str,
                "count": len(articles),
                "titles": [a.get("japanese_title") or a.get("title", "") for a in articles[:3]],
            })
        except (json.JSONDecodeError, KeyError):
            continue

    # 週次サマリーの一覧
    weekly_files = sorted(articles_dir.glob("weekly-*.html"), reverse=True)
    weeklies = []
    for wf in weekly_files:
        week_id = wf.stem.replace("weekly-", "")
        weeklies.append({"id": week_id, "filename": wf.name})

    # 週ごとにグループ化（日曜始まり〜土曜終わり）
    weeks = {}  # key: 週の日曜日の日付文字列
    for day in days:
        dt = datetime.strptime(day["date"], "%Y-%m-%d")
        week_sunday = get_week_start(dt)
        week_key = week_sunday.strftime("%Y-%m-%d")
        weeks.setdefault(week_key, []).append(day)

    # 週を新しい順にソート
    sorted_weeks = sorted(weeks.keys(), reverse=True)

    # 各週のHTMLをJSONデータとして埋め込む
    weeks_data = []
    for week_key in sorted_weeks:
        week_days = sorted(weeks[week_key], key=lambda d: d["date"], reverse=True)
        sunday = datetime.strptime(week_key, "%Y-%m-%d")
        saturday = sunday + timedelta(days=6)
        label = f"{sunday.strftime('%m/%d')}〜{saturday.strftime('%m/%d')}"
        weeks_data.append({
            "key": week_key,
            "label": label,
            "days": week_days,
        })

    # サイドメニューHTML
    sidebar_html = ""
    if weeklies:
        sidebar_items = "".join(
            f'<a href="articles/{w["filename"]}" class="sidebar-link">{w["id"]}</a>'
            for w in weeklies
        )
        sidebar_html = sidebar_items

    # メインコンテンツ: 全週のカードをページとして生成（JSで切り替え）
    weeks_json = json.dumps(weeks_data, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIニュースまとめ - 毎日のIT・テクノロジーニュースをAIが要約</title>
  <meta name="description" content="最新のIT・テクノロジーニュースをAIが毎日自動収集・要約。背景解説や今後の予測まで、忙しいあなたのためのニュースダイジェスト。">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8f9fa; color: #111; }}
    .site-header {{ padding: 2rem 1rem 1rem; text-align: center; border-bottom: 1px solid #e5e5e5; background: #fff; }}
    .site-header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 6px; }}
    .site-header p {{ font-size: 14px; color: #666; }}
    .layout {{ display: flex; max-width: 1100px; margin: 0 auto; min-height: calc(100vh - 200px); }}
    .sidebar {{ width: 220px; padding: 1.5rem 1rem; border-right: 1px solid #e5e5e5; background: #fff; flex-shrink: 0; }}
    .sidebar h2 {{ font-size: 14px; font-weight: 600; color: #555; margin-bottom: 12px; }}
    .sidebar-link {{ display: block; padding: 8px 12px; font-size: 13px; color: #1a73e8; text-decoration: none; border-radius: 6px; margin-bottom: 4px; }}
    .sidebar-link:hover {{ background: #f0f4ff; }}
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
    }}
  </style>
</head>
<body>
  <div class="site-header">
    <h1>AIニュースまとめ</h1>
    <p>最新のIT・テクノロジーニュースをAIが毎日自動収集・要約</p>
  </div>

  <div class="layout">
    <aside class="sidebar">
      <h2>週次サマリー</h2>
      {sidebar_html}
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
    const weeks = {weeks_json};
    let currentPage = 0;

    const weekdays = ["日", "月", "火", "水", "木", "金", "土"];

    function renderWeek() {{
      const week = weeks[currentPage];
      document.getElementById("week-label").textContent = week.label;
      document.getElementById("btn-prev").disabled = (currentPage >= weeks.length - 1);
      document.getElementById("btn-next").disabled = (currentPage <= 0);

      const container = document.getElementById("articles-container");
      container.innerHTML = "";

      week.days.forEach(day => {{
        const dt = new Date(day.date + "T00:00:00");
        const wd = weekdays[dt.getDay()];
        const display = dt.getFullYear() + "\\u5E74" + (dt.getMonth()+1) + "\\u6708" + dt.getDate() + "\\u65E5";

        let titlesHtml = day.titles.map(t => "<li>" + t + "</li>").join("");
        if (day.count > 3) {{
          titlesHtml += '<li class="more">...\\u4ED6' + (day.count - 3) + '\\u4EF6</li>';
        }}

        const card = document.createElement("a");
        card.href = "articles/" + day.date + ".html";
        card.className = "day-card";
        card.innerHTML = '<div class="day-date">' + display + '\\uFF08' + wd + '\\uFF09</div>'
          + '<div class="day-count">' + day.count + '\\u4EF6\\u306E\\u8A18\\u4E8B</div>'
          + '<ul class="day-titles">' + titlesHtml + '</ul>';
        container.appendChild(card);
      }});
    }}

    function prevWeek() {{
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

    renderWeek();
  </script>
</body>
</html>'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"index.html を生成しました（{len(days)}日分、{len(sorted_weeks)}週）")


if __name__ == "__main__":
    generate_index()
