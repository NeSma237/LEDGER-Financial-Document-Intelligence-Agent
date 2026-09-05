import sys
import json
import shutil
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("usage: python move_duplicates.py JSON_data")
        sys.exit(1)

    json_data_dir = Path(sys.argv[1])
    report_path = Path("duplicate_report.json")

    if not report_path.exists():
        print(f"❌ {report_path} is missing. Please run find_duplicates.py first.")
        sys.exit(1)

    report = json.loads(report_path.read_text(encoding="utf-8"))

    duplicates_dir = json_data_dir.parent / f"{json_data_dir.name}_duplicates"
    duplicates_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    missing = 0

    for group in report:
        for doc_id in group["duplicates_of_it"]:
            src = json_data_dir / f"{doc_id}.json"
            if not src.exists():
                print(f"⚠️  the file is missing: {src.name}")
                missing += 1
                continue

            dst = duplicates_dir / src.name
            shutil.move(str(src), str(dst))
            moved += 1

    print(f"\n✅  {moved} files moved to {duplicates_dir}")
    if missing:
        print(f"⚠️  {missing} files were missing (we ignored them)")

    remaining = len(list(json_data_dir.glob('*.json')))
    print(f"📦 files remaining in {json_data_dir}: {remaining}")


if __name__ == "__main__":
    main()