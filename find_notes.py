import glob
import io
import json

KEYWORDS = [
    "フィクション",
    "注記",
    "⚠",
    "確認されていない",
    "未確認",
    "訓練データ",
    "私の知識",
    "現時点（2025",
    "2025年時点",
    "実在しない",
    "架空",
]

FIELDS = ["ai_interpretation", "background", "prediction",
          "market_impact", "japanese_title"]

found = {}

for path in sorted(glob.glob("articles/**/*.json", recursive=True)):
    try:
        data = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        continue
    items = data if isinstance(data, list) else data.get("articles", [])
    if not isinstance(items, list):
        continue
    for a in items:
        if not isinstance(a, dict):
            continue
        for f in FIELDS:
            v = a.get(f)
            if not isinstance(v, str):
                continue
            for k in KEYWORDS:
                if k in v:
                    found.setdefault(k, []).append(
                        (path, f, a.get("japanese_title", "")[:30]))
                    break

for k in KEYWORDS:
    rows = found.get(k, [])
    if rows:
        print(f"\n■ 「{k}」: {len(rows)}件")
        for path, field, title in rows[:10]:
            print(f"   {path} [{field}] {title}")

print(f"\n合計キーワード種別: {len([k for k in found])}")
# --- end of file ---