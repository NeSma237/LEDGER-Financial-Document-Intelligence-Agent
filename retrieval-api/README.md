# retrieval-api

## المسؤولية
فهرسة المحتوى المستخرج وتوفير بحث دلالي (semantic) + بحث غير دلالي (BM25/metadata) + reranking.

## Framework
FastAPI + Vector DB (FAISS / Qdrant / Chroma)

## المتطلبات
- [ ] Chunking ذكي (section-aware / table-aware / parent-child) — مش fixed-size عادي
- [ ] حفظ metadata على كل chunk: document_id, page, section, content_type
- [ ] بحث dense (embeddings) + بحث non-vector واحد على الأقل (BM25 مثلاً)
- [ ] Over-retrieve ثم rerank (مثال: top-30 → reranker → top-5)
- [ ] تقييم قيمة الـ reranking فعليًا (قبل/بعد) مش افتراض إنه بيحسّن

## التشغيل محليًا
```bash
# TODO
```
