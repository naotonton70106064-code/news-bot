import glob
import io
import json

DRY_RUN = False

removed_total = 0

for path in sorted(glob.glob("articles/**/*.json", recursive=True)):
    try:
        data = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        continue

    is_list = isinstance(data, list)
    items = data if is_list else data.get("articles", [])
    if not isinstance(items, list):
        continue

    keep = []
    removed = []
    for a in items:
        if not isinstance(a, dict):
            keep.append(a)
            continue
        # ai_interpretation が注記で始まる = 中身が無い記事
        ai = a.get("ai_interpretation") or ""
        if ai.lstrip().startswith("⚠"):
            removed.append(a.get("japanese_title", "")[:40])
        else:
            keep.append(a)

    if removed:
        removed_total += len(removed)
        print(f"--- {path}  {len(items)}件 → {len(keep)}件")
        for t in removed:
            print(f"    削除: {t}")
        if not DRY_RUN:
            if is_list:
                data = keep
            else:
                data["articles"] = keep
            with io.open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)

print(f"\n削除対象: {removed_total}記事")
print("DRY_RUN =", DRY_RUN)
# --- end of file ---