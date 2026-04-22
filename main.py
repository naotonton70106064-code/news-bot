import json
import os
from datetime import datetime
from collector import collect_articles
from summarizer import summarize_article

def main():
    print("ニュース収集を開始します...")
    articles = collect_articles()
    print(f"{len(articles)}件の記事を収集しました")
    
    results = []
    
    for i, article in enumerate(articles):
        print(f"要約中... ({i+1}/{len(articles)}) {article['title'][:40]}...")
        summary = summarize_article(article)
        
        results.append({
            "title": article["title"],
            "url": article["url"],
            "source": article["source"],
            "summary": summary,
            "collected_at": datetime.now().isoformat(),
        })
    
    # JSONファイルに保存
    filename = f"news_{datetime.now().strftime('%Y%m%d')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    dashboard_file = generate_dashboard(results)

    print(f"\n完了！{filename}に保存しました")

def generate_dashboard(results):
    import json as json_module
    
    with open("dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    articles_json = json_module.dumps(results, ensure_ascii=False, indent=2)
    html = html.replace("__ARTICLES__", articles_json)
    
    output_filename = f"dashboard_{datetime.now().strftime('%Y%m%d')}.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"ダッシュボード生成: {output_filename}")
    return output_filename

if __name__ == "__main__":
    main()