import os
import json
import re
from dotenv import load_dotenv
from summarizer import client

load_dotenv()

JUDGE_MODEL = "claude-sonnet-4-6"

# Sonnet の料金（$/トークン）
IN_PRICE = 3.0 / 1_000_000
OUT_PRICE = 15.0 / 1_000_000
JPY = 150  # 円換算の概算レート

JUDGE_PROMPT = """あなたはニュース記事の事実確認を行う校閲者です。

以下の【提供文書】だけを根拠として、【判定対象の文】を判定してください。

【提供文書】
{documents}

【判定対象の文】
{sentence}

判定は次の2つを独立して行います。どちらも必ず実施してください。

━━ 判定A: ラベル ━━

文に「事実の主張」が含まれるかを見ます。
文末が解釈的（「〜とみられる」「〜を示している」）でも、
文中に事実の記述が含まれていればそれを対象とします。

優先順位の高い順に判定してください。

1. "hedged" — 「一般に〜とされる」「〜と言われている」等で
   提供文書の情報ではないと明示している部分がある場合。
   文末が解釈的でもこちらを優先します。

2. "unsupported" — 提供文書に根拠のない具体的な事実
   （数値・固有名詞・取引・日付・出来事）が含まれる場合。
   これが最も重要な検出対象です。

3. "supported" — 事実の記述があり、その根拠が提供文書にある場合。
   文末が解釈的でも、事実部分に根拠があればこちらとします。

4. "opinion" — 事実の記述を含まず、解釈・評価・見通しだけの場合。
   （例:「このニュースの本質は〜にある」「〜と読み取れる」）

━━ 判定B: 帰属（ラベルに関わらず必ず実施） ━━

「過去記事では」「6月時点では」のように、
特定の文書に帰属させて内容を述べているかを見ます。

帰属させている場合、その内容がその文書に実際に書かれているかを確認し、
書かれていなければ misattributed を true にしてください。

重要:
- 複数の文書を比較すること自体は問題ではありません。
- 問題なのは、ある文書の内容を別の文書の内容として述べることだけです。
  （例: 今日の記事にしかない「機密申請」を、過去記事の内容として述べる）
- 帰属を示していない文は misattributed = false です。

JSONだけを出力してください。説明文は不要です。

{{"label": "hedged|unsupported|supported|opinion", "misattributed": true|false, "evidence": "根拠の引用（無ければ空文字）", "reason": "判定理由を1文で"}}
"""


def split_sentences(text):
    """生成結果から判定対象の文を取り出す。
    見出し行（【】で始まる）と空行は除外する。"""
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("【") or line.startswith("---"):
            continue
        line = re.sub(r"^[・\-\*]\s*", "", line)
        line = re.sub(r"^\d+\.\s*", "", line)
        for s in re.split(r"(?<=。)", line):
            s = s.strip()
            if len(s) >= 10:
                lines.append(s)
    return lines


def judge(documents, sentence):
    """1文を判定する。判定結果と (入力トークン, 出力トークン) を返す。"""
    prompt = JUDGE_PROMPT.format(documents=documents, sentence=sentence)
    message = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    usage = (message.usage.input_tokens, message.usage.output_tokens)
    try:
        return json.loads(text), usage
    except json.JSONDecodeError:
        return ({"label": "parse_error", "misattributed": False,
                 "evidence": "", "reason": text[:200]}, usage)


if __name__ == "__main__":
    documents = open("judge_documents.txt", encoding="utf-8").read()
    article = open("judge_article.txt", encoding="utf-8").read()

    sentences = split_sentences(article)
    print(f"判定対象: {len(sentences)}文\n")

    results = []
    counts = {}
    misattr = 0
    total_in = 0
    total_out = 0

    for i, s in enumerate(sentences, 1):
        r, (tin, tout) = judge(documents, s)
        total_in += tin
        total_out += tout

        label = r.get("label", "?")
        ma = r.get("misattributed", False)
        counts[label] = counts.get(label, 0) + 1
        if ma:
            misattr += 1

        if label == "unsupported" or ma:
            mark = "NG"
        elif label == "opinion":
            mark = "op"
        elif label == "hedged":
            mark = "~ "
        else:
            mark = "  "

        print(f"[{mark}] {i:2d}. {label}{' / 帰属誤り' if ma else ''}")
        print(f"      {s[:60]}")
        if label == "unsupported" or ma:
            print(f"      → {r.get('reason', '')}")
        results.append({"sentence": s, **r})

    print("\n=== 集計 ===")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    print(f"  帰属誤り: {misattr}")

    cost = total_in * IN_PRICE + total_out * OUT_PRICE
    print("\n=== コスト ===")
    print(f"  API呼び出し: {len(sentences)}回")
    print(f"  入力トークン: {total_in:,}")
    print(f"  出力トークン: {total_out:,}")
    print(f"  1記事あたり: ${cost:.4f}（約{cost * JPY:.1f}円）")
    print(f"  毎朝20記事なら月: ${cost * 20 * 30:.2f}（約{cost * 20 * 30 * JPY:,.0f}円）")

    with open("judge_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\njudge_result.json に保存しました")
# --- end of file ---