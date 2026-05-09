import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from collector import collect_articles, collect_all, FEEDS
from summarizer import summarize_article

JST = ZoneInfo("Asia/Tokyo")


def now_jst():
    return datetime.now(JST)


def parse_summary(summary_text, category="it"):
    sections = {
        "japanese_title": "",
        "summary_lines": [],
        "background": "",
        "market_impact": "",
        "points": [],
        "prediction": "",
        "ai_interpretation": ""
    }

    current_section = None
    lines = summary_text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "【日本語タイトル】" in line:
            current_section = "japanese_title"
        elif "【3行要約】" in line:
            current_section = "summary"
        elif "【背景・経緯】" in line:
            current_section = "background"
        elif "【市場への影響】" in line:
            current_section = "market_impact"
        elif "【注目ポイント】" in line:
            current_section = "points"
        elif "【今後の予測】" in line:
            current_section = "prediction"
        elif "【AIの解釈】" in line:
            current_section = "ai_interpretation"
        elif current_section == "japanese_title" and line:
            sections["japanese_title"] = line
        elif current_section == "summary" and (line.startswith("1.") or line.startswith("2.") or line.startswith("3.")):
            sections["summary_lines"].append(line)
        elif current_section == "background":
            sections["background"] += line + " "
        elif current_section == "market_impact":
            sections["market_impact"] += line + " "
        elif current_section == "points" and line.startswith("・"):
            sections["points"].append(line)
        elif current_section == "prediction":
            sections["prediction"] += line + " "
        elif current_section == "ai_interpretation":
            sections["ai_interpretation"] += line + " "

    return sections


def generate_article_page(results, category="it"):
    with open("dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    articles_json = json.dumps(results, ensure_ascii=False, indent=2)
    html = html.replace("__ARTICLES__", articles_json)

    # articles/{category}/ ディレクトリに保存
    articles_dir = Path("articles") / category
    articles_dir.mkdir(parents=True, exist_ok=True)

    date_str = now_jst().strftime('%Y-%m-%d')
    output_filename = articles_dir / f"{date_str}.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  記事ページ生成: {output_filename}")
    return str(output_filename)


def process_category(category, articles):
    """1カテゴリ分の記事を要約・保存する"""
    cat_name = FEEDS[category]["name"]
    print(f"\n[{cat_name}] 要約中...")

    results = []
    for i, article in enumerate(articles):
        print(f"  ({i+1}/{len(articles)}) {article['title'][:40]}...")
        summary_text = summarize_article(article, category)
        parsed = parse_summary(summary_text, category)

        result = {
            "title": article["title"],
            "japanese_title": parsed["japanese_title"],
            "url": article["url"],
            "source": article["source"],
            "category": category,
            "summary_lines": parsed["summary_lines"],
            "points": parsed["points"],
            "prediction": parsed["prediction"].strip(),
            "ai_interpretation": parsed["ai_interpretation"].strip(),
            "collected_at": now_jst().isoformat(),
        }

        # カテゴリに応じたフィールド
        if category == "it":
            result["background"] = parsed["background"].strip()
        else:
            result["market_impact"] = parsed["market_impact"].strip()

        results.append(result)

    # JSON保存
    articles_dir = Path("articles") / category
    articles_dir.mkdir(parents=True, exist_ok=True)

    date_str = now_jst().strftime('%Y-%m-%d')
    filename = articles_dir / f"{date_str}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"  JSON保存: {filename}")
    generate_article_page(results, category)

    return results


def main():
    print("ニュース収集を開始します...")
    all_articles = collect_all()

    for category, articles in all_articles.items():
        if articles:
            process_category(category, articles)
        else:
            print(f"\n[{FEEDS[category]['name']}] 記事なし - スキップ")

    print("\n全カテゴリの処理が完了しました")


if __name__ == "__main__":
    main()
