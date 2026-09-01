# LEDGER — Financial Document Intelligence Agent

نظام Agentic RAG بيقرأ تقارير مالية (PDF) ويجاوب على أسئلة عنها مع دليل (citation) لكل إجابة، من غير hallucination.

## المعمارية

المشروع مبني كـ 7 microservices منفصلة بتتكلم عن طريق HTTP:

| # | الخدمة | الفريمورك | المسؤول |
|---|---|---|---|
| 1 | `orchestrator-api` | FastAPI | TBD |
| 2 | `doc-processor-api` | FastAPI + OCR/Layout model | TBD |
| 3 | `retrieval-api` | FastAPI + Vector DB | TBD |
| 4 | `agent-service` | LangGraph | TBD |
| 5 | `eval-service` | FastAPI + Langfuse | TBD |
| 6 | `ui-service` | Gradio | TBD |
| 7 | `answer-validator-api` | FastAPI/Flask | TBD |

## تشغيل المشروع

```bash
# TODO: تعليمات التشغيل (Docker Compose أو startup script)
```

## هيكل الريبو

```
ledger-repo/
├── orchestrator-api/       # العصب المركزي - بيوجه الطلبات بين الخدمات
├── doc-processor-api/      # تحويل PDF خام لتمثيل منظم (نص/جداول/صفحات)
├── retrieval-api/          # البحث الدلالي + BM25 + reranking
├── agent-service/          # الـ "Brain" - LangGraph agent
├── eval-service/           # التقييم والـ tracing (Langfuse)
├── ui-service/             # واجهة Gradio (chat + dashboard)
├── answer-validator-api/   # التحقق من شكل الإجابة (schema validation)
├── docs/                   # مستندات المشروع (schema, API contracts, failure analysis)
├── docker-compose.yml      # (اختياري - bonus)
└── README.md
```

## الداتا
- [TAT-DQA Dataset](https://huggingface.co/datasets/next-tat/TAT-DQA) — للـ Document Intelligence
- `questions_setA_practice` (100 سؤال) — لاختبار الـ RAG pipeline

⚠️ **قاعدة مهمة**: الـ ingestion pipeline لازم ياخد الـ PDFs الخام كمدخل، ممنوع استخدام الـ pre-parsed JSON بتاع الداتاست كتمثيل للمستند في الإنتاج.

## Branching Strategy
- `main` — محمي، مفيش push مباشر
- فروع الميزات: `feature/<service-name>-<short-desc>` (مثال: `feature/retrieval-chunking`)
- فروع الإصلاحات: `bugfix/<short-desc>`
- كل الدمج عن طريق Pull Requests فقط

## Definition of Done
راجعي [`docs/definition-of-done.md`](docs/definition-of-done.md)
