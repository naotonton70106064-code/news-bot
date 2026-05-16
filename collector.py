import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser

JST = ZoneInfo("Asia/Tokyo")
COLLECTED_URLS_FILE = Path("collected_urls.json")

# カテゴリ別RSSフィード（各ソースに新規取得件数 limit を指定）
FEEDS = {
    "it": {
        "name": "IT・テクノロジー",
        "sources": [
            {"url": "https://techcrunch.com/feed/", "limit": 3},
            {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "limit": 2},
            {"url": "https://xtech.nikkei.com/rss/index.rdf", "limit": 2},
        ],
    },
    "japan_economy": {
        "name": "日本経済",
        "sources": [
            # ロイター日本語（公式RSSは廃止のためGoogleニュースのsite:jp.reuters.com検索を代替）
            {"url": "https://news.google.com/rss/search?q=site:jp.reuters.com+when:7d&hl=ja&gl=JP&ceid=JP:ja", "limit": 3},
            {"url": "https://www.nhk.or.jp/rss/news/cat4.xml", "limit": 2},
            {"url": "https://toyokeizai.net/list/feed/rss", "limit": 2},
        ],
    },
    "world_economy": {
        "name": "世界経済",
        "sources": [
            # Reuters英語（公式RSSは廃止のためGoogleニュースのsite:reuters.com検索を代替）
            {"url": "https://news.google.com/rss/search?q=site:reuters.com+business+when:7d&hl=en-US&gl=US&ceid=US:en", "limit": 3},
            {"url": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "limit": 2},
            # AP News Business（rsshub.appが403のためGoogleニュースのsite:apnews.com検索を代替）
            {"url": "https://news.google.com/rss/search?q=site:apnews.com+business+when:7d&hl=en-US&gl=US&ceid=US:en", "limit": 2},
        ],
    },
}


def load_collected_urls():
    """過去に取得済みのURL一覧を読み込む。形式は {url: collected_at_iso} の辞書。"""
    if not COLLECTED_URLS_FILE.exists():
        return {}
    try:
        with open(COLLECTED_URLS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            # 旧形式（URLのリスト）から辞書へ移行
            return {url: "" for url in data}
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [警告] {COLLECTED_URLS_FILE} の読み込みに失敗: {e}")
        return {}


def save_collected_urls(collected_urls):
    """取得済みURLをJSONファイルに保存する。"""
    with open(COLLECTED_URLS_FILE, "w", encoding="utf-8") as f:
        json.dump(collected_urls, f, ensure_ascii=False, indent=2)


def collect_articles(category="it", collected_urls=None):
    """指定カテゴリの記事を収集する。collected_urlsに含まれるURLはスキップ。"""
    if category not in FEEDS:
        raise ValueError(f"Unknown category: {category}")

    if collected_urls is None:
        collected_urls = load_collected_urls()

    feed_config = FEEDS[category]
    articles = []

    for source in feed_config["sources"]:
        feed_url = source["url"]
        limit = source["limit"]
        try:
            feed = feedparser.parse(feed_url)
            picked = 0
            skipped = 0
            for entry in feed.entries:
                if picked >= limit:
                    break
                url = entry.link
                if url in collected_urls:
                    skipped += 1
                    continue
                article = {
                    "title": entry.title,
                    "url": url,
                    "summary": entry.get("summary", ""),
                    "source": feed.feed.get("title", feed_url),
                    "category": category,
                }
                articles.append(article)
                picked += 1
            if skipped:
                print(f"  [情報] {feed_url}: 取得済み{skipped}件をスキップ")
        except Exception as e:
            print(f"  [警告] {feed_url} の取得に失敗: {e}")
            continue

    return articles


def collect_all():
    """全カテゴリの記事を収集し、新規取得URLを記録する。"""
    collected_urls = load_collected_urls()
    all_articles = {}
    for category in FEEDS:
        print(f"[{FEEDS[category]['name']}] 収集中...")
        all_articles[category] = collect_articles(category, collected_urls)
        print(f"  {len(all_articles[category])}件収集")

    # 新たに取得したURLを記録して保存
    now_iso = datetime.now(JST).isoformat()
    new_count = 0
    for articles in all_articles.values():
        for article in articles:
            if article["url"] not in collected_urls:
                collected_urls[article["url"]] = now_iso
                new_count += 1
    if new_count:
        save_collected_urls(collected_urls)
        print(f"[情報] {new_count}件のURLを{COLLECTED_URLS_FILE}に記録")

    return all_articles


if __name__ == "__main__":
    all_articles = collect_all()
    for cat, articles in all_articles.items():
        print(f"\n=== {FEEDS[cat]['name']} ===")
        for i, article in enumerate(articles):
            print(f"  {i+1}. {article['title'][:50]}")
