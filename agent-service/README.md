# agent-service

## المسؤولية
"العقل المفكر" — بياخد السؤال، يقرر إيه الأدوات المطلوبة، ويطلع إجابة متوافقة مع الـ schema مع الدليل الداعم.

## Framework
LangGraph (إجباري للـ orchestration الأساسي للـ reasoning graph)

## Tools المطلوبة (deterministic)
- `search_documents(query)`
- `search_tables(query)`
- `calculate(expression)` — أي حساب رياضي لازم يعدي من هنا، ممنوع الموديل يحسب من دماغه
- `filter_documents(metadata)`

## متطلبات الـ Graph
- [ ] Conditional branches حقيقية: نص vs جدول vs سؤال رقمي
- [ ] فحص كفاية الدليل (sufficient vs insufficient evidence)
- [ ] Retry logic لو الدليل ضعيف
- [ ] ممنوع يكون fixed chain (node1 → node2 → node3) بدون فروع حقيقية

## الموديل
LLM خفيف/كفؤ في tool-calling (مثال: Qwen2.5, Llama-3.1-8B-Instruct, Phi-3.5, أو API خارجي رخيص لو مسموح)

## التشغيل محليًا
```bash
# TODO
```
