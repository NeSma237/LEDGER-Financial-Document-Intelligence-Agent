"""
test_full_pipeline.py
========================
"""
import sys
import json
import requests

from docling_adapter import adapt_docling_output
from schemas import IndexRequest

DOC_PROCESSOR_URL = "http://127.0.0.1:8000/process"   # port doc-processor-api بتاعها
RETRIEVAL_INDEX_URL = "http://127.0.0.1:8002/index"   # port retrieval-api بتاعك (لو مختلف عدّليه)


def main():
    if len(sys.argv) < 2:
        print("usage: python test_full_pipeline.py path/to/file.pdf")
        return

    pdf_path = sys.argv[1]

    # 1.send the PDF to doc-processor-api
    print(f"📤 sending {pdf_path} to doc-processor-api...")
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path, f, "application/pdf")}
        try:
            resp = requests.post(DOC_PROCESSOR_URL, files=files, timeout=300)
        except requests.exceptions.ConnectionError:
            print(f"❌ can't connect to {DOC_PROCESSOR_URL}")
            print("   ❌ please make sure doc-processor-api is running: uvicorn main:app --reload --port 8000")
            return

    if resp.status_code != 200:
        print(f"❌ doc-processor-api returned error: {resp.status_code}")
        print(resp.text[:500])
        return

    docling_output = resp.json()
    document_id = docling_output.get("document_id", "unknown_doc")
    raw_dict = docling_output.get("raw_docling_dict", {})
    print(f"✅ sent the PDF and received a response. document_id={document_id}")
    print(f"   number of text elements: {len(raw_dict.get('texts', []))}")
    print(f"   number of tables: {len(raw_dict.get('tables', []))}")

    # 2. convert the docling output to the retrieval-api schema
    print("\n🔄 converting the docling output to the retrieval-api schema...")
    adapted = adapt_docling_output(document_id, raw_dict)

    total_sections = sum(len(p["sections"]) for p in adapted["pages"])
    print(f"✅ converted to {len(adapted['pages'])} pages, with {total_sections} sections in total")

    # print a sample of the first 5 sections
    print("\n📋 sample from the first 5 sections:")
    count = 0
    for page in adapted["pages"]:
        for section in page["sections"]:
            if count >= 5:
                break
            preview = (section.get("text") or str(section.get("table")))[:80]
            print(f"   Page {page['page_number']} | {section['content_type']:6} | {section['section_title']:20} | {preview}")
            count += 1
        if count >= 5:
            break

    # 3.make sure the adapted output conforms to the IndexRequest schema
    print("\n✅ making sure the adapted output conforms to the IndexRequest schema...")
    try:
        validated = IndexRequest(**adapted)
        print(f"✅ conforms to the schema! ({len(validated.pages)} pages)")
    except Exception as e:
        print(f"❌ does not conform to the schema: {e}")
        return

    # 4. send the adapted output to retrieval-api for indexing
    print(f"\n📥 trying to send to retrieval-api at {RETRIEVAL_INDEX_URL}...")
    try:
        index_resp = requests.post(RETRIEVAL_INDEX_URL, json=adapted, timeout=120)
        if index_resp.status_code == 200:
            print(f"✅ indexed successfully: {index_resp.json()}")
        else:
            print(f"⚠️  retrieval-api returned error: {index_resp.status_code} — {index_resp.text[:300]}")
    except requests.exceptions.ConnectionError:
        print("⚠️  retrieval-api is not running — skipping the actual indexing step.")
        print("   (this is not an error, the basic test [conversion + validation] has passed)")


if __name__ == "__main__":
    main()
