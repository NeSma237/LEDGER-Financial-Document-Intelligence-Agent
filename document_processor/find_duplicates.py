"""
find_duplicates.py
====================
بيدور على كل ملفات JSON في فولدر معين، وبيقارن الـ markdown_content
بتاعهم (نفس المحتوى = نفس المستند حتى لو الـ document_id مختلف)،
ويطلعلك تقرير بكل المجموعات المكررة.

الاستخدام:
    python find_duplicates.py /path/to/JSON_data
"""

import sys
import json
import hashlib
import glob
from pathlib import Path
from collections import defaultdict


def main():
    if len(sys.argv) < 2:
        print("usage: python find_duplicates.py /path/to/JSON_data")
        sys.exit(1)

    folder = Path(sys.argv[1])
    files = [
        p for p in folder.glob("*.json")
        if "-checkpoint" not in p.stem
    ]

    by_hash = defaultdict(list)

    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  couldn't read {fp.name}: {e}")
            continue

        markdown = data.get("markdown_content", "")
        content_hash = hashlib.md5(markdown.encode("utf-8")).hexdigest()
        by_hash[content_hash].append(data.get("document_id", fp.stem))

    duplicate_groups = {h: ids for h, ids in by_hash.items() if len(ids) > 1}
    total_dupe_files = sum(len(ids) for ids in duplicate_groups.values())

    print(f"📦 total files: {len(files)}")
    print(f"🔑 unique content: {len(by_hash)}")
    print(f"👯 duplicate groups: {len(duplicate_groups)}")
    print(f"📄 total files involved in duplicates: {total_dupe_files}\n")

    if duplicate_groups:
        print(" duplicate groups:")
        report = []
        for h, ids in duplicate_groups.items():
            print(f"  - {ids}")
            report.append({"keep": ids[0], "duplicates_of_it": ids[1:]})

        Path("duplicate_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("\n📝 the full report is saved in duplicate_report.json")


if __name__ == "__main__":
    main()