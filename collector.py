import feedparser

# 収集するRSSフィードのリスト
FEEDS = [
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/wired/index",
]

def collect_articles():
    articles = []
    
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:3]:  # 各サイトから3記事ずつ
            article = {
                "title": entry.title,
                "url": entry.link,
                "summary": entry.get("summary", ""),
                "source": feed.feed.title,
            }
            articles.append(article)
    
    return articles

if __name__ == "__main__":
    articles = collect_articles()
    
    for i, article in enumerate(articles):
        print(f"--- 記事{i+1} ---")
        print(f"タイトル: {article['title']}")
        print(f"URL: {article['url']}")
        print(f"ソース: {article['source']}")
        print()