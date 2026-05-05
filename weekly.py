"""週次サマリーを自動生成するスクリプト"""
import json
from datetime import datetime, timedelta
from pathlib import Path


def get_week_range(target_date=None):
    """対象週の月曜〜日曜の日付範囲を返す（前週）"""
    if target_date is None:
        target_date = datetime.now()
    # 前週の月曜日
    monday = target_date - timedelta(days=target_date.weekday() + 7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def load_week_articles(monday, sunday):
    """指定週のJSON記事を全て読み込む"""
    articles_dir = Path("articles")
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

    return all_articles


def generate_weekly_summary(articles, monday, sunday):
    """週次サマリーHTMLを生成"""
    week_num = monday.isocalendar()[1]
    year = monday.year
    week_id = f"{year}-W{week_num:02d}"

    monday_str = monday.strftime("%Y年%m月%d日")
    sunday_str = sunday.strftime("%Y年%m月%d日")

    # ソース別に記事を分類
    by_source = {}
    for a in articles:
        source = a.get("source", "不明")
        by_source.setdefault(source, []).append(a)

    # 記事リストHTML
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

    # トピックハイライト（背景情報が長い記事＝重要な記事を上位5件抽出）
    ranked = sorted(articles, key=lambda a: len(a.get("background", "")), reverse=True)
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
  <title>週次サマリー {week_id}（{monday_str}〜{sunday_str}）- AIニュースまとめ</title>
  <meta name="description" content="{week_id}のIT・テクノロジーニュース週次まとめ。{len(articles)}件の記事をAIが分析・要約。">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8f9fa; color: #111; padding: 2rem 1rem; }}
    .header {{ max-width: 800px; margin: 0 auto 2rem; }}
    .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    .header .period {{ font-size: 14px; color: #666; }}
    .header .stats {{ font-size: 13px; color: #888; margin-top: 8px; }}
    .back-link {{ display: inline-block; margin-bottom: 1rem; font-size: 13px; color: #1a73e8; text-decoration: none; }}
    .back-link:hover {{ text-decoration: underline; }}
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
    <a href="../index.html" class="back-link">&larr; トップに戻る</a>
    <div class="header">
      <h1>週次サマリー {week_id}</h1>
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

    # 保存
    articles_dir = Path("articles")
    output_file = articles_dir / f"weekly-{week_id}.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"週次サマリー生成: {output_file}（{len(articles)}件）")
    return str(output_file)


def main():
    monday, sunday = get_week_range()
    print(f"対象期間: {monday.strftime('%Y-%m-%d')} 〜 {sunday.strftime('%Y-%m-%d')}")

    articles = load_week_articles(monday, sunday)
    if not articles:
        print("対象週の記事が見つかりませんでした。")
        return

    generate_weekly_summary(articles, monday, sunday)


if __name__ == "__main__":
    main()
