# eval-service

## المسؤولية
تتبع كل خطوة في الـ pipeline (tracing) + تشغيل benchmark تلقائي على عينة held-out من TAT-DQA.

## Framework
FastAPI + Langfuse

## المتطلبات
- [ ] Tracing: query classification, retrieval, reranking, tool calls, generation, verification — كل خطوة بالـ latency والـ prompts والـ token usage
- [ ] Benchmark: Exact Match, F1, numerical accuracy + Recall@K/Precision@K للـ retrieval
- [ ] استخدام Langfuse datasets/experiments لمقارنة variants (مثال: chunking strategy on/off, reranker on/off)
- [ ] Failure analysis: 5 أمثلة فشل على الأقل + السبب الجذري لكل واحدة

## التشغيل محليًا
```bash
# TODO
```
