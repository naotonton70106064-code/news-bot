import glob
import io
import json
import re

# AIの自己注記が始まる位置を示すパターン
NOTE_PATTERNS = [
    r"\s*-{2,}\s*>?\s*⚠",      # --- ⚠ / --- > ⚠
    r"\s*-{2,}\s*\*{0,2}注記",   # --- **注記
    r"\s*⚠",                    # 単独の⚠から始まる
]

FIELDS = ["ai_interpretation", "background", "prediction",
          "market_impact", "japanese_title"]

DRY_RUN = False   # True の間は書き換えない


def find_cut(text):
    """注記の開始位置を返す。無ければ None。"""
    best = None
    for pat in NOTE_PATTERNS:
        m = re.search(pat, text)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


changed_files = 0
changed_fields = 0

for path in sorted(glob.glob("articles/**/*.json", recursive=True)):
    try:
        data = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        continue

    items = data if isinstance(data, list) else data.get("articles", [])
    if not isinstance(items, list):
        continue

    touched = False
    for a in items:
        if not isinstance(a, dict):
            continue
        for f in FIELDS:
            v = a.get(f)
            if not isinstance(v, str):
                continue
            cut = find_cut(v)
            if cut is None:
                continue
            before = v[:cut].rstrip()
            if len(before) < 50:
                print(f"!!! {path} [{f}] 残りが{len(before)}字しかない。スキップ")
                print()
                continue
            print(f"--- {path} [{f}]")
            print(f"  残す末尾: ...{before[-50:]}")
            print(f"  削る部分: {v[cut:cut+100].strip()[:100]}...")
            print()
            changed_fields += 1
            touched = True
            if not DRY_RUN:
                a[f] = before

    if touched:
        changed_files += 1
        if not DRY_RUN:
            with io.open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)

print(f"\n対象: {changed_files}ファイル / {changed_fields}フィールド")
print("DRY_RUN =", DRY_RUN)
# --- end of file ---