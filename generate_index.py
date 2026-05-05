"""記事一覧ページ（index.html）を自動生成するスクリプト"""
import json
from pathlib import Path
from datetime import datetime


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
        # weekly-2026-W18.html -> 2026-W18
        week_id = wf.stem.replace("weekly-", "")
        weeklies.append({"id": week_id, "filename": wf.name})

    # HTML生成
    days_html = ""
    for day in days:
        titles_html = "".join(
            f'<li>{t}</li>' for t in day["titles"]
        )
        if day["count"] > 3:
            titles_html += f'<li class="more">...他{day["count"] - 3}件</li>'

        dt = datetime.strptime(day["date"], "%Y-%m-%d")
        display_date = dt.strftime("%Y年%m月%d日")
        weekday = ["月", "火", "水", "木", "金", "土", "日"][dt.weekday()]

        days_html += f'''
    <a href="articles/{day["date"]}.html" class="day-card">
      <div class="day-date">{display_date}（{weekday}）</div>
      <div class="day-count">{day["count"]}件の記事</div>
      <ul class="day-titles">{titles_html}</ul>
    </a>'''

    weekly_html = ""
    if weeklies:
        weekly_items = "".join(
            f'<a href="articles/{w["filename"]}" class="weekly-link">{w["id"]}</a>'
            for w in weeklies
        )
        weekly_html = f'''
    <section class="weekly-section">
      <h2>週次サマリー</h2>
      <div class="weekly-list">{weekly_items}</div>
    </section>'''

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIニュースまとめ - 毎日のIT・テクノロジーニュースをAIが要約</title>
  <meta name="description" content="最新のIT・テクノロジーニュースをAIが毎日自動収集・要約。背景解説や今後の予測まで、忙しいあなたのためのニュースダイジェスト。">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8f9fa; color: #111; padding: 2rem 1rem; }}
    .site-header {{ max-width: 800px; margin: 0 auto 2rem; text-align: center; }}
    .site-header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; }}
    .site-header p {{ font-size: 14px; color: #666; }}
    .nav {{ max-width: 800px; margin: 0 auto 2rem; display: flex; gap: 12px; justify-content: center; font-size: 13px; }}
    .nav a {{ color: #1a73e8; text-decoration: none; }}
    .nav a:hover {{ text-decoration: underline; }}
    .container {{ max-width: 800px; margin: 0 auto; }}
    .day-card {{ display: block; background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1.25rem; margin-bottom: 12px; text-decoration: none; color: inherit; transition: box-shadow 0.2s; }}
    .day-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .day-date {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
    .day-count {{ font-size: 12px; color: #888; margin-bottom: 8px; }}
    .day-titles {{ list-style: none; font-size: 13px; color: #444; line-height: 1.8; }}
    .day-titles .more {{ color: #888; }}
    .weekly-section {{ margin-bottom: 2rem; }}
    .weekly-section h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 12px; }}
    .weekly-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .weekly-link {{ display: inline-block; padding: 8px 16px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 13px; color: #1a73e8; text-decoration: none; }}
    .weekly-link:hover {{ background: #f0f4ff; }}
    .footer {{ max-width: 800px; margin: 3rem auto 0; text-align: center; font-size: 11px; color: #aaa; line-height: 1.8; }}
    .footer a {{ color: #888; text-decoration: none; }}
    .footer a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="site-header">
    <h1>AIニュースまとめ</h1>
    <p>最新のIT・テクノロジーニュースをAIが毎日自動収集・要約</p>
  </div>
  <nav class="nav">
    <a href="privacy.html">プライバシーポリシー</a>
    <a href="about.html">運営者情報</a>
    <a href="contact.html">お問い合わせ</a>
  </nav>
  <div class="container">
    {weekly_html}
    <section>
      <h2 style="font-size:18px;font-weight:600;margin-bottom:12px;">記事一覧</h2>
      {days_html}
    </section>
  </div>
  <div class="footer">
    <p>本サイトの解釈・予測はAIによる見解であり、投資助言・専門的アドバイスではありません。</p>
    <p><a href="privacy.html">プライバシーポリシー</a> | <a href="about.html">運営者情報</a> | <a href="contact.html">お問い合わせ</a></p>
  </div>
</body>
</html>'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"index.html を生成しました（{len(days)}日分の記事一覧）")


if __name__ == "__main__":
    generate_index()
