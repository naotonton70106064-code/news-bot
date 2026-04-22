import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def summarize_article(article):
    prompt = f"""
以下のニュース記事を日本語で要約してください。

タイトル: {article['title']}
内容: {article['summary']}

以下の形式で答えてください：
【3行要約】
1. 
2. 
3. 

【背景・ポイント】
（2〜3文で）
"""
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

if __name__ == "__main__":
    from collector import collect_articles
    
    articles = collect_articles()
    
    # まず1記事だけ試す
    article = articles[0]
    print(f"タイトル: {article['title']}")
    print()
    summary = summarize_article(article)
    print(summary)