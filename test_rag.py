import os
from dotenv import load_dotenv
from db import get_connection
from summarizer import client, PROMPTS

load_dotenv()

TARGET_ID = 779        # 検証する記事のID
MAX_PAST = 2           # 渡す過去記事の最大数
MAX_DISTANCE = 0.35    # これより遠いものは渡さない


def fetch_target(conn, article_id):
    row = conn.execute("""
        SELECT id,
               COALESCE(japanese_title, title),
               legacy_summary,
               category,
               article_date,
               summary_lines,
               points
        FROM articles
        WHERE id = %s
    """, (article_id,)).fetchone()
    return row


def fetch_past(conn, article_id, limit, max_distance):
    rows = conn.execute("""
        SELECT id,
               COALESCE(japanese_title, title),
               legacy_summary,
               article_date,
               embedding <=> (SELECT embedding FROM articles WHERE id = %s) AS distance,
               summary_lines
        FROM articles
        WHERE id <> %s
          AND article_date < (SELECT article_date FROM articles WHERE id = %s)
          AND embedding <=> (SELECT embedding FROM articles WHERE id = %s) < %s
        ORDER BY distance
        LIMIT %s
    """, (article_id, article_id, article_id, article_id, max_distance, limit)).fetchall()
    return rows


def render_content(summary_lines, points, legacy_summary):
    """summary_lines(JSONB配列)を本文テキストに組み立てる。
    旧形式の記事では legacy_summary にフォールバックする。"""
    parts = []
    if summary_lines:
        parts.extend(summary_lines)
    if points:
        parts.append("")
        parts.extend(points)
    if not parts and legacy_summary:
        parts.append(legacy_summary)
    return "\n".join(parts)


def build_past_block(rows):
    lines = ["", "---", "【参考: 過去の関連記事】"]
    for r in rows:
        lines.append(f"- {r[3]}: {r[1]}")
        body = render_content(r[5], None, r[2])
        if body:
            lines.append("  " + body.replace("\n", "\n  "))
    lines.append("""
上記の過去記事と比較して、変化した点があれば以下の形式で追記してください。

【過去からの変化】
（何がどう変わったかを1〜2文で。過去記事に書かれていないことは書かないこと）

変化が無い、または関連が薄い場合は、この見出しごと出力しないでください。
""")
    return "\n".join(lines)


def build_constraint_block():
    """提供情報の外から書かれることを抑える制約。
    事実を書く項目は厳しく、解釈の項目は出所を明示させる。"""
    return """
---
【記述に関する制約】

以下を厳守してください。

1. 【3行要約】【過去からの変化】には、上で提供された情報に書かれている内容だけを書く。
   提供情報に無い数値・企業名・取引・時期は書かない。

2. 【背景・経緯】【注目ポイント】【今後の予測】【AIの解釈】で、
   提供情報に無い一般的な文脈を補う場合は、
   「一般に〜とされる」「〜と言われている」のように、
   提供情報ではないと読者が判別できる書き方にする。

3. 具体的な数値・固有名詞・取引・日付・年を、提供情報の裏付けなしに書かない。
   提供情報から論理的に導ける場合も、具体的な年・日付・金額は書かない。
   「2026年中でない」という情報から「2027年以降」と書くようなことをしない。
   時期に言及する場合は「当面」「時期未定」のように、
   提供情報の範囲を超えない表現にする。
   一般論として書く場合も、確認できない具体名は出さない。

4. 【過去からの変化】で過去記事の内容を述べるときは、
   その過去記事に実際に書かれている表現の範囲にとどめる。
   今日の記事に書かれている情報を、過去記事の内容として書かない。
   複数の記事の記述を統合して、一方の記事の内容として述べない。

"""


with get_connection() as conn:
    target = fetch_target(conn, TARGET_ID)
    print("=== 対象記事 ===")
    print(f"[{target[4]}] {target[1]}")
    print()

    past = fetch_past(conn, TARGET_ID, MAX_PAST, MAX_DISTANCE)
    print(f"=== 関連する過去記事: {len(past)}件 ===")
    for r in past:
        print(f"  距離 {r[4]:.4f} [{r[3]}] {r[1]}")
    print()

prompt = PROMPTS.get(target[3], PROMPTS["it"]).format(
    title=target[1],
    summary=render_content(target[5], target[6], target[2]),
)
if past:
    prompt += build_past_block(past)
prompt += build_constraint_block()

print("=== 送信するプロンプト ===")
print(prompt)
print()
print("=== 生成結果 ===")

RUNS = 5
NG_WORDS = ["2027", "機密申請を完了", "機密IPO申請を完了"]

for i in range(RUNS):
    print(f"\n{'=' * 20} {i + 1}回目 {'=' * 20}")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text

    hits = [w for w in NG_WORDS if w in text]
    if hits:
        print(f"  [NG] 検出: {', '.join(hits)}")
    else:
        print("  [OK] NGワードなし")

    print(text)
# --- end of file ---