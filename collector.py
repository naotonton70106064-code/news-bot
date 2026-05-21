import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser

JST = ZoneInfo("Asia/Tokyo")
COLLECTED_URLS_FILE = Path("collected_urls.json")

# ITカテゴリのキーワードフィルタ（タイトル/概要のいずれかに含まれればOK）
# Wired/Ars Technicaなど汎用フィードからIT関連記事のみを抽出するために使う。
# 英語キーワードは単語境界でマッチ（"ai"が"again"にマッチしないようにするため）。
# 日本語キーワードは部分一致（単語境界の概念がないため）。
IT_KEYWORDS_EN = [
    "ai", "ml", "tech", "software", "hardware", "app", "startup",
    "cloud", "data", "cyber", "robot", "chip", "gpu", "api",
]
IT_KEYWORDS_JA = [
    "テクノロジー", "スタートアップ", "ソフトウェア", "クラウド",
    "データ", "サイバー", "ロボット", "半導体",
]
_IT_KEYWORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in IT_KEYWORDS_EN) + r")\b",
    re.IGNORECASE,
)

# カテゴリ別RSSフィード（各ソースに新規取得件数 limit を指定）
# filter=True のソースは IT_KEYWORDS によるキーワードフィルタを適用する。
FEEDS = {
    "it": {
        "name": "IT・テクノロジー",
        "sources": [
            {"url": "https://techcrunch.com/feed/", "limit": 3, "filter": False},
            {"url": "https://www.wired.com/feed/category/business/latest/rss", "limit": 2, "filter": True},
            {"url": "https://feeds.arstechnica.com/arstechnica/index", "limit": 2, "filter": True},
        ],
    },
    "japan_economy": {
        "name": "日本経済",
        "sources": [
            {"url": "https://www.nhk.or.jp/rss/news/cat4.xml", "limit": 7},
        ],
    },
    "world_economy": {
        "name": "世界経済",
        "sources": [
            {"url": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "limit": 3},
            {"url": "https://feeds.npr.org/1006/rss.xml", "limit": 2},
            {"url": "https://feeds.bbci.co.uk/news/business/rss.xml", "limit": 2},
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


def _matches_it_keywords(title, summary):
    """タイトルまたは概要にITキーワードのいずれかが含まれていれば True。"""
    text = f"{title} {summary}"
    if _IT_KEYWORD_RE.search(text):
        return True
    return any(keyword in text for keyword in IT_KEYWORDS_JA)


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
        apply_filter = source.get("filter", False)
        try:
            feed = feedparser.parse(feed_url)
            picked = 0
            skipped = 0
            filtered = 0
            for entry in feed.entries:
                if picked >= limit:
                    break
                url = entry.link
                if url in collected_urls:
                    skipped += 1
                    continue
                title = entry.title
                summary = entry.get("summary", "")
                if apply_filter and not _matches_it_keywords(title, summary):
                    filtered += 1
                    continue
                article = {
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "source": feed.feed.get("title", feed_url),
                    "category": category,
                }
                articles.append(article)
                picked += 1
            if skipped:
                print(f"  [情報] {feed_url}: 取得済み{skipped}件をスキップ")
            if filtered:
                print(f"  [情報] {feed_url}: キーワード不一致{filtered}件をスキップ")
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
