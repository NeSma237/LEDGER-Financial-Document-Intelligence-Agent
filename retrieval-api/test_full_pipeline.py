"""
test_full_pipeline.py
========================
سكريبت تكامل حقيقي (end-to-end) بين doc-processor-api (بتاع MounReda)
و retrieval-api (بتاعك). بيعمل الآتي بالترتيب:

    1. يبعت PDF حقيقي لـ doc-processor-api (/process)
    2. ياخد raw_docling_dict من الرد
    3. يحوله بالـ docling_adapter لشكل الـ schema بتاعتك
    4. يتحقق منه (IndexRequest) عشان نتأكد إنه هيتقبل
    5. يبعته فعليًا لـ retrieval-api (/index) لو السيرفر ده شغال كمان

طريقة التشغيل:
    1. شغّلي doc-processor-api في terminal أول (على البورت بتاعه)
    2. (اختياري) شغّلي retrieval-api في terminal تاني لو عايزة الخطوة
       الأخيرة (الفهرسة الفعلية) تحصل كمان
    3. شغّلي السكريبت ده من terminal تالت:
         python test_full_pipeline.py "path/to/any.pdf"
"""
import sys
import json
import requests

from docling_adapter import adapt_docling_output
from schemas import IndexRequest

DOC_PROCESSOR_URL = "http://127.0.0.1:8000/process"   # بورت doc-processor-api بتاعها
RETRIEVAL_INDEX_URL = "http://127.0.0.1:8002/index"   # بورت retrieval-api بتاعك (لو مختلف عدّليه)


def main():
    if len(sys.argv) < 2:
        print("استخدام: python test_full_pipeline.py path/to/file.pdf")
        return

    pdf_path = sys.argv[1]

    # 1. ابعتي الـ PDF لـ doc-processor-api
    print(f"📤 بنبعت {pdf_path} لـ doc-processor-api...")
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path, f, "application/pdf")}
        try:
            resp = requests.post(DOC_PROCESSOR_URL, files=files, timeout=300)
        except requests.exceptions.ConnectionError:
            print(f"❌ مش قادر أوصل لـ {DOC_PROCESSOR_URL}")
            print("   تأكدي إن doc-processor-api شغال على البورت ده.")
            return

    if resp.status_code != 200:
        print(f"❌ doc-processor-api رجّع error: {resp.status_code}")
        print(resp.text[:500])
        return

    docling_output = resp.json()
    document_id = docling_output.get("document_id", "unknown_doc")
    raw_dict = docling_output.get("raw_docling_dict", {})
    print(f"✅ استلمنا الرد. document_id={document_id}")
    print(f"   عدد عناصر texts: {len(raw_dict.get('texts', []))}")
    print(f"   عدد الجداول: {len(raw_dict.get('tables', []))}")

    # 2. حوّلي الشكل بالـ adapter
    print("\n🔄 بنحول الشكل بالـ docling_adapter...")
    adapted = adapt_docling_output(document_id, raw_dict)

    total_sections = sum(len(p["sections"]) for p in adapted["pages"])
    print(f"✅ طلع {len(adapted['pages'])} صفحة، فيهم {total_sections} section إجمالي")

    # اطبعي أول كام section كعينة
    print("\n📋 عينة من أول 5 sections:")
    count = 0
    for page in adapted["pages"]:
        for section in page["sections"]:
            if count >= 5:
                break
            preview = (section.get("text") or str(section.get("table")))[:80]
            print(f"   صفحة {page['page_number']} | {section['content_type']:6} | {section['section_title']:20} | {preview}")
            count += 1
        if count >= 5:
            break

    # 3. اتأكدي إنه متوافق مع الـ schema
    print("\n✅ بنتحقق من الـ schema...")
    try:
        validated = IndexRequest(**adapted)
        print(f"✅ متوافق تمامًا! ({len(validated.pages)} صفحة)")
    except Exception as e:
        print(f"❌ مش متوافق مع الـ schema: {e}")
        return

    # 4. (اختياري) ابعتيه فعليًا لـ retrieval-api لو شغال
    print(f"\n📥 بنحاول نبعت لـ retrieval-api على {RETRIEVAL_INDEX_URL}...")
    try:
        index_resp = requests.post(RETRIEVAL_INDEX_URL, json=adapted, timeout=120)
        if index_resp.status_code == 200:
            print(f"✅ اتفهرس بنجاح: {index_resp.json()}")
        else:
            print(f"⚠️  retrieval-api رجّع: {index_resp.status_code} — {index_resp.text[:300]}")
    except requests.exceptions.ConnectionError:
        print("⚠️  retrieval-api مش شغال دلوقتي — تخطينا خطوة الفهرسة الفعلية.")
        print("   (ده مش خطأ، الاختبار الأساسي [التحويل + التحقق] نجح فوق)")


if __name__ == "__main__":
    main()
