import feedparser

# カテゴリ別RSSフィード
FEEDS = {
    "it": {
        "name": "IT・テクノロジー",
        "sources": [
            "https://techcrunch.com/feed/",
            "https://xtech.nikkei.com/rss/index.rdf",
        ],
    },
    "japan_economy": {
        "name": "日本経済",
        "sources": [
            "https://toyokeizai.net/list/feed/rss",
            "https://assets.wor.jp/rss/rdf/nikkei/news.rdf",
        ],
    },
    "world_economy": {
        "name": "世界経済",
        "sources": [
            "https://www.reuters.com/rssFeed/worldNews",
            "https://www.bloomberg.co.jp/feeds/sitemap_news.xml",
        ],
    },
}


def collect_articles(category="it"):
    """指定カテゴリの記事を収集する"""
    if category not in FEEDS:
        raise ValueError(f"Unknown category: {category}")

    feed_config = FEEDS[category]
    articles = []

    for feed_url in feed_config["sources"]:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:  # 各サイトから3記事ずつ
                article = {
                    "title": entry.title,
                    "url": entry.link,
                    "summary": entry.get("summary", ""),
                    "source": feed.feed.get("title", feed_url),
                    "category": category,
                }
                articles.append(article)
        except Exception as e:
            print(f"  [警告] {feed_url} の取得に失敗: {e}")
            continue

    return articles


def collect_all():
    """全カテゴリの記事を収集する"""
    all_articles = {}
    for category in FEEDS:
        print(f"[{FEEDS[category]['name']}] 収集中...")
        all_articles[category] = collect_articles(category)
        print(f"  {len(all_articles[category])}件収集")
    return all_articles


if __name__ == "__main__":
    all_articles = collect_all()
    for cat, articles in all_articles.items():
        print(f"\n=== {FEEDS[cat]['name']} ===")
        for i, article in enumerate(articles):
            print(f"  {i+1}. {article['title'][:50]}")
