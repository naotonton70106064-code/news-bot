import os
import requests
from dotenv import load_dotenv
import math


load_dotenv()

API_KEY = os.getenv("VOYAGE_API_KEY")
if not API_KEY:
    raise SystemExit("VOYAGE_API_KEY が読めていません")

texts = [
    "OpenAIが新しい言語モデルを発表した",
    "Anthropicが次世代AIを公開した",
    "日銀が政策金利の引き上げを決定した",
]

res = requests.post(
    "https://api.voyageai.com/v1/embeddings",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "voyage-4-lite",
        "input": texts,
        "input_type": "document",
    },
    timeout=30,
)

print("status:", res.status_code)
if res.status_code != 200:
    print(res.text)
    raise SystemExit(1)

data = res.json()
vectors = [d["embedding"] for d in data["data"]]

print("返ってきた件数:", len(vectors))
print("次元数:", len(vectors[0]))
print("先頭5個:", vectors[0][:5])
print("usage:", data.get("usage"))

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)

print()
print("OpenAI vs Anthropic:", round(cosine(vectors[0], vectors[1]), 4))
print("OpenAI vs 日銀     :", round(cosine(vectors[0], vectors[2]), 4))
print("Anthropic vs 日銀  :", round(cosine(vectors[1], vectors[2]), 4))