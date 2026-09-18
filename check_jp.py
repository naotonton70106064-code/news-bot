import glob
import io
import json

total = 0
thin = 0
doseki = 0
notes = 0
samples = []

for path in sorted(glob.glob("articles/world_economy/*.json")):
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
        total += 1
        title = a.get("japanese_title") or a.get("title") or ""
        summary = a.get("summary") or a.get("legacy_summary") or ""
        ai = a.get("ai_interpretation") or ""

        if "動静" in title:
            doseki += 1
        if len(summary) < 60:
            thin += 1
            if len(samples) < 10:
                samples.append((len(summary), title[:45]))
        if "⚠" in ai or "注記" in ai:
            notes += 1

print(f"記事総数: {total}")
print(f"  うち「動静」: {doseki} ({doseki/total*100:.1f}%)")
print(f"  うち本文60字未満: {thin} ({thin/total*100:.1f}%)")
print(f"  うちAI注記あり: {notes}")
print("\n本文が短い記事の例:")
for n, t in samples:
    print(f"  {n:3d}字  {t}")
# --- end of file ---