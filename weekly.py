"""週次サマリーを自動生成するスクリプト（カテゴリ対応）"""
import json
from datetime import datetime, timedelta
from pathlib import Path

CATEGORIES = ["it", "japan_economy", "world_economy"]
CATEGORY_NAMES = {
    "it": "IT・テクノロジー",
    "japan_economy": "日本経済",
    "world_economy": "世界経済",
}


def get_week_range(target_date=None):
    """対象週の月曜〜日曜の日付範囲を返す（前週）"""
    if target_date is None:
        target_date = datetime.now()
    monday = target_date - timedelta(days=target_date.weekday() + 7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def load_week_articles(monday, sunday, category):
    """指定週・カテゴリのJSON記事を全て読み込む"""
    articles_dir = Path("articles") / category
    all_articles = []

    current = monday
    while current <= sunday:
        date_str = current.strftime("%Y-%m-%d")
        json_file = articles_dir / f"{date_str}.json"
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                day_articles = json.load(f)
                for a in day_articles:
                    a["date"] = date_str
                all_articles.extend(day_articles)
        current += timedelta(days=1)

    # 旧構造（articles/直下）もITとして読み込む
    if category == "it":
        legacy_dir = Path("articles")
        current = monday
        while current <= sunday:
            date_str = current.strftime("%Y-%m-%d")
            json_file = legacy_dir / f"{date_str}.json"
            if json_file.exists():
                with open(json_file, "r", encoding="utf-8") as f:
                    day_articles = json.load(f)
                    for a in day_articles:
                        a["date"] = date_str
                    all_articles.extend(day_articles)
            current += timedelta(days=1)

    return all_articles


def generate_weekly_summary(articles, monday, sunday, category):
    """週次サマリーHTMLを生成"""
    week_num = monday.isocalendar()[1]
    year = monday.year
    week_id = f"{year}-W{week_num:02d}"
    cat_name = CATEGORY_NAMES[category]

    monday_str = monday.strftime("%Y年%m月%d日")
    sunday_str = sunday.strftime("%Y年%m月%d日")

    by_source = {}
    for a in articles:
        source = a.get("source", "不明")
        by_source.setdefault(source, []).append(a)

    articles_html = ""
    for date_key in sorted(set(a["date"] for a in articles)):
        day_articles = [a for a in articles if a["date"] == date_key]
        dt = datetime.strptime(date_key, "%Y-%m-%d")
        display_date = dt.strftime("%m/%d")
        weekday = ["月", "火", "水", "木", "金", "土", "日"][dt.weekday()]

        articles_html += f'<div class="day-group"><h3>{display_date}（{weekday}）</h3><ul>'
        for a in day_articles:
            title = a.get("japanese_title") or a.get("title", "")
            articles_html += f'<li><span class="source-tag">{a.get("source", "")}</span> {title}</li>'
        articles_html += "</ul></div>"

    # 重要記事の抽出
    ranked = sorted(articles, key=lambda a: len(a.get("background", "") + a.get("market_impact", "")), reverse=True)
    highlights = ranked[:5]
    highlights_html = ""
    for a in highlights:
        title = a.get("japanese_title") or a.get("title", "")
        summary = " ".join(a.get("summary_lines", []))
        highlights_html += f'''
        <div class="highlight-card">
          <div class="highlight-title">{title}</div>
          <div class="highlight-summary">{summary}</div>
          <div class="highlight-prediction"><strong>今後の予測:</strong> {a.get("prediction", "")}</div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{cat_name} 週次サマリー {week_id}（{monday_str}〜{sunday_str}）- AIニュースまとめ</title>
  <meta name="description" content="{week_id}の{cat_name}ニュース週次まとめ。{len(articles)}件の記事をAIが分析・要約。">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8f9fa; color: #111; padding: 2rem 1rem; }}
    .header {{ max-width: 800px; margin: 0 auto 2rem; }}
    .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    .header .period {{ font-size: 14px; color: #666; }}
    .header .stats {{ font-size: 13px; color: #888; margin-top: 8px; }}
    .back-link {{ display: inline-flex; align-items: center; min-height: 44px; padding: 10px 18px; background: #fff; border: 1px solid #ddd; border-radius: 8px; color: #333; font-size: 14px; text-decoration: none; line-height: 1.2; margin-bottom: 1rem; }}
    .back-link:hover {{ background: #f0f0f0; }}
    .back-link:active {{ background: #e8e8e8; }}
    .container {{ max-width: 800px; margin: 0 auto; }}
    .section {{ margin-bottom: 2rem; }}
    .section h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #e5e5e5; }}
    .highlight-card {{ background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 1.25rem; margin-bottom: 12px; }}
    .highlight-title {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; }}
    .highlight-summary {{ font-size: 13px; color: #444; line-height: 1.7; margin-bottom: 8px; }}
    .highlight-prediction {{ font-size: 12px; color: #666; line-height: 1.6; }}
    .day-group {{ margin-bottom: 1rem; }}
    .day-group h3 {{ font-size: 14px; font-weight: 600; color: #333; margin-bottom: 6px; }}
    .day-group ul {{ list-style: none; }}
    .day-group li {{ font-size: 13px; color: #444; line-height: 2; }}
    .source-tag {{ display: inline-block; font-size: 10px; padding: 1px 6px; background: #eee; border-radius: 4px; color: #666; margin-right: 4px; }}
    .footer {{ max-width: 800px; margin: 3rem auto 0; text-align: center; font-size: 11px; color: #aaa; }}
  </style>
</head>
<body>
  <div class="container">
    <a href="../../index.html?cat={category}" class="back-link">&larr; 一覧に戻る</a>
    <div class="header">
      <h1>{cat_name} 週次サマリー {week_id}</h1>
      <div class="period">{monday_str} 〜 {sunday_str}</div>
      <div class="stats">記事数: {len(articles)}件 / ソース: {len(by_source)}サイト</div>
    </div>

    <div class="section">
      <h2>今週の注目トピック</h2>
      {highlights_html}
    </div>

    <div class="section">
      <h2>全記事一覧</h2>
      {articles_html}
    </div>
  </div>
  <div class="footer">
    <p>本サイトの解釈・予測はAIによる見解であり、投資助言・専門的アドバイスではありません。</p>
  </div>
</body>
</html>'''

    articles_dir = Path("articles") / category
    articles_dir.mkdir(parents=True, exist_ok=True)
    output_file = articles_dir / f"weekly-{week_id}.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [{cat_name}] 週次サマリー生成: {output_file}（{len(articles)}件）")
    return str(output_file)


def main():
    monday, sunday = get_week_range()
    print(f"対象期間: {monday.strftime('%Y-%m-%d')} 〜 {sunday.strftime('%Y-%m-%d')}")

    for category in CATEGORIES:
        articles = load_week_articles(monday, sunday, category)
        if not articles:
            print(f"  [{CATEGORY_NAMES[category]}] 記事なし - スキップ")
            continue
        generate_weekly_summary(articles, monday, sunday, category)


if __name__ == "__main__":
    main()
