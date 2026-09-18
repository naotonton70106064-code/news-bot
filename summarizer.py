import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 全カテゴリ共通の制約。
# 2026-09-19 追加:
# AIが記事内に「2026年は未来の日付であり実在しない情報」「本文が空欄のため
# 分析が不可能」といった自己注記を書き込み、それがそのまま公開されていた。
# AdSenseの「有用性の低いコンテンツ」による不承認の一因。
COMMON_CONSTRAINTS = """

【出力に関する制約】

1. 記事の真偽・日付・実在性について言及しないこと。
   「未来の日付である」「学習データの範囲外」「架空の可能性がある」
   「実在しない情報」といった注記・免責事項を書かないこと。
   提供された記事は事実として扱うこと。

2. 情報が不足していることを記事内に書かないこと。
   「本文が空欄のため分析できない」「情報が限られているため推論を含む」
   といった断り書きを書かないこと。

3. 情報が少ない場合は、書ける範囲で簡潔にまとめること。
   無理に埋めようとして推測を重ねないこと。

4. 指定された見出し以外の見出し・注記・区切り線（---）を出力しないこと。
"""

# カテゴリ別プロンプトテンプレート
PROMPTS = {
    "it": """
以下のニュース記事を日本語で分析してください。

タイトル: {title}
内容: {summary}

以下の形式で厳密に答えてください：

【日本語タイトル】
（SEOを意識した日本語タイトルを1行で）

【3行要約】
1.
2.
3.

【背景・経緯】
（このニュースが起きた背景を2〜3文で）

【注目ポイント】
・
・
・

【今後の予測】
（今後どうなりそうか2〜3文で）

【AIの解釈】
（このニュースの本質的な意味・示唆を2〜3文で）
""",
    "japan_economy": """
以下の経済ニュース記事を日本語で分析してください。

タイトル: {title}
内容: {summary}

以下の形式で厳密に答えてください：

【日本語タイトル】
（SEOを意識した日本語タイトルを1行で）

【3行要約】
1.
2.
3.

【市場への影響】
（株式市場・為替・国内産業への影響を2〜3文で）

【注目ポイント】
・
・
・

【今後の予測】
（今後の経済動向・政策への影響を2〜3文で）

【AIの解釈】
（このニュースの本質的な意味・日本経済への示唆を2〜3文で）
""",
    "world_economy": """
以下の世界経済ニュース記事を日本語で分析してください。

タイトル: {title}
内容: {summary}

以下の形式で厳密に答えてください：

【日本語タイトル】
（SEOを意識した日本語タイトルを1行で）

【3行要約】
1.
2.
3.

【市場への影響】
（グローバル市場・為替・主要産業への影響を2〜3文で）

【注目ポイント】
・
・
・

【今後の予測】
（今後の世界経済・地政学的影響を2〜3文で）

【AIの解釈】
（このニュースの本質的な意味・グローバル経済への示唆を2〜3文で）
""",
}


def summarize_article(article, category="it"):
    prompt_template = PROMPTS.get(category, PROMPTS["it"])
    prompt = prompt_template.format(
        title=article["title"],
        summary=article["summary"],
    )
    prompt += COMMON_CONSTRAINTS

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text


if __name__ == "__main__":
    from collector import collect_articles

    articles = collect_articles("it")
    article = articles[0]
    print(f"タイトル: {article['title']}")
    print()
    summary = summarize_article(article, "it")
    print(summary)
# --- end of file ---