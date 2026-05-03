import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def summarize_article(article):
    prompt = f"""
以下のニュース記事を日本語で分析してください。

タイトル: {article['title']}
内容: {article['summary']}

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
"""

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

    articles = collect_articles()
    article = articles[0]
    print(f"タイトル: {article['title']}")
    print()
    summary = summarize_article(article)
    print(summary)