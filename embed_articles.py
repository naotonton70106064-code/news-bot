import os
import time
import requests
from dotenv import load_dotenv
from db import get_connection

load_dotenv()

API_KEY = os.getenv("VOYAGE_API_KEY")
if not API_KEY:
    raise SystemExit("VOYAGE_API_KEY が読めていません")

LIMIT = None          # 全件。少量テストしたいときだけ 10 などに変える
BATCH_SIZE = 100
SLEEP_BETWEEN_BATCH = 3   # レート制限に当たらないための待機（秒）


def embed(texts, max_retries=5):
    for attempt in range(max_retries):
        res = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": "voyage-4-lite",
                "input": texts,
                "input_type": "document",
            },
            timeout=60,
        )
        if res.status_code == 429:
            print(f"  応答: {res.text[:300]}")
            wait = 2 ** attempt * 5
            print(f"  429。{wait}秒待機してリトライ({attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        res.raise_for_status()
        return [d["embedding"] for d in res.json()["data"]]
    raise SystemExit("リトライ上限に達しました。時間をおいて再実行してください")


def build_text(title, japanese_title, summary_lines, points, legacy_summary):
    """埋め込む本文を組み立てる。
    処理済み記事は summary_lines(JSONB配列)に要約が入っている。
    legacy_summary は旧形式の記事用のフォールバック。"""
    parts = [japanese_title or title]
    if summary_lines:
        parts.extend(summary_lines)
    if points:
        parts.extend(points)
    if not summary_lines and legacy_summary:
        parts.append(legacy_summary)
    return "\n".join(parts)[:4000]


with get_connection() as conn:
    sql = """
        SELECT id, title, japanese_title, summary_lines, points, legacy_summary
        FROM articles
        WHERE embedding IS NULL
        ORDER BY id
    """
    if LIMIT:
        sql += f" LIMIT {LIMIT}"

    rows = conn.execute(sql).fetchall()
    print(f"対象: {len(rows)}件")

    done = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        texts = [build_text(r[1], r[2], r[3], r[4], r[5]) for r in chunk]
        vectors = embed(texts)

        with conn.cursor() as cur:
            for (row, vec) in zip(chunk, vectors):
                cur.execute(
                    "UPDATE articles SET embedding = %s WHERE id = %s",
                    (str(vec), row[0]),
                )
        conn.commit()
        done += len(chunk)
        print(f"  {done}/{len(rows)} 完了")
        time.sleep(SLEEP_BETWEEN_BATCH)

print("done")
# --- end of file ---