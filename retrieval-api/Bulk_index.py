import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

from docling_adapter import adapt_docling_output
from chunking import chunk_document
from schemas import IndexRequest
import vector_store
import bm25_index

BATCH_SIZE_DOCS = 50  # كام مستند نجمع قبل ما نعمل flush فعلي للـ indexes
PROGRESS_FILE = Path("bulk_index_progress.json")
FAILURES_FILE = Path("bulk_index_failures.json")


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
    return set()


def save_progress(done_ids: set) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(sorted(done_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_failures(failures: List[Dict[str, str]]) -> None:
    FAILURES_FILE.write_text(
        json.dumps(failures, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def flush_batch(chunk_buffer: List[Dict[str, Any]]) -> int:
    if not chunk_buffer:
        return 0
    vector_store.add_chunks(chunk_buffer)
    bm25_index.add_chunks(chunk_buffer)
    return len(chunk_buffer)


def process_one_file(json_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    document_id = data.get("document_id") or json_path.stem
    raw_docling_dict = data["raw_docling_dict"]

    adapted = adapt_docling_output(document_id, raw_docling_dict)

    # نفس التحقق اللي main.py بيعمله وقت /index — لو فيه مستند مش مطابق للسكيما
    # هنعرف بدري من غير ما نضيع وقت في الفهرسة
    validated = IndexRequest(**adapted)
    pages_as_dicts = [page.model_dump() for page in validated.pages]

    return chunk_document(validated.document_id, pages_as_dicts)


def main():
    if len(sys.argv) < 2:
        print("usage: python bulk_index.py /path/to/JSON_data")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    if not input_dir.is_dir():
        print(f"❌  {input_dir} is not a directory")
        sys.exit(1)

    # بنستبعد ملفات الـ checkpoint (زي *-checkpoint.json اللي بتيجي من Jupyter)
    all_files = sorted(
        p for p in input_dir.glob("*.json") if "-checkpoint" not in p.stem
    )

    done_ids = load_progress()
    files_to_process = [p for p in all_files if p.stem not in done_ids]

    print(f"📦 total files: {len(all_files)}")
    print(f"✅ already indexed (from previous run): {len(done_ids)}")
    print(f"🔜 remaining: {len(files_to_process)}\n")

    if not files_to_process:
        print("all files are already indexed. Nothing to do.")
        return

    failures: List[Dict[str, str]] = []
    chunk_buffer: List[Dict[str, Any]] = []
    ids_in_buffer: List[str] = []
    total_chunks_indexed = 0
    start_time = time.time()

    for i, json_path in enumerate(files_to_process, start=1):
        try:
            chunks = process_one_file(json_path)
        except Exception as e:
            failures.append({"file": json_path.name, "error": f"{type(e).__name__}: {e}"})
            print(f"   ⚠️  failed: {json_path.name} — {e}")
            continue

        if not chunks:
            # مستند من غير محتوى قابل للفهرسة (مفيهوش نص ولا جدول)
            failures.append({"file": json_path.name, "error": "no chunks produced (empty content)"})
            done_ids.add(json_path.stem)  # منعتبروش نرجعله تاني كل مرة
            continue

        chunk_buffer.extend(chunks)
        ids_in_buffer.append(json_path.stem)

        if len(ids_in_buffer) >= BATCH_SIZE_DOCS:
            total_chunks_indexed += flush_batch(chunk_buffer)
            done_ids.update(ids_in_buffer)
            save_progress(done_ids)
            save_failures(failures)

            elapsed = time.time() - start_time
            print(
                f"[{i}/{len(files_to_process)}] indexed {len(done_ids)} documents so far "
                f"({total_chunks_indexed} chunks) — {elapsed:.0f}s"
            )
            chunk_buffer, ids_in_buffer = [], []

    # flush آخر دفعة متبقية أقل من BATCH_SIZE_DOCS
    if ids_in_buffer:
        total_chunks_indexed += flush_batch(chunk_buffer)
        done_ids.update(ids_in_buffer)
        save_progress(done_ids)
        save_failures(failures)

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"✅ finished indexing in {elapsed:.0f} seconds")
    print(f"   documents marked as done: {len(done_ids)}")
    print(f"   total chunks added in this session: {total_chunks_indexed}")
    print(f"   failures/empty content in this session: {len(failures)}  (details in {FAILURES_FILE})")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()