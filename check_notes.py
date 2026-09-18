import glob
import io
import json
import re

# AIの自己注記を示すパターン
PATTERNS = [
    r"⚠",
    r"注記[:：]",
    r"フィクションや未確認",
    r"公式に確認されていない",
    r"現時点（20\d\d年",
]

FIELDS = ["ai_interpretation", "background", "prediction",
          "market_impact", "japanese_title", "legacy_summary"]

hits = []

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
            for pat in PATTERNS:
                m = re.search(pat, v)
                if m:
                    start = max(0, m.start() - 30)
                    hits.append((path, f, v[start:m.start() + 200]))
                    break

print(f"該当: {len(hits)}箇所 / ファイル{len(set(h[0] for h in hits))}件\n")

for path, field, snippet in hits:
    print(f"--- {path} [{field}]")
    print(f"    {snippet}\n")
# --- end of file ---