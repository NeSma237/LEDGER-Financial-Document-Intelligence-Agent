# API Contracts بين الخدمات

> يتفق عليها الفريق كله بدري قبل ما كل واحد يبدأ في جزئه — أي تغيير هنا لازم يتناقش مع أصحاب الخدمات المتأثرة.

## orchestrator-api ↔ doc-processor-api
- `POST /process` — بياخد PDF، بيرجع التمثيل المنظم (نص/جداول/صفحات)

## orchestrator-api ↔ retrieval-api
- `POST /index` — بيستقبل التمثيل المنظم ويفهرسه
- `POST /search` — بياخد query، بيرجع أفضل chunks بعد الـ reranking

## orchestrator-api ↔ agent-service
- `POST /agent/answer` — بياخد `{"question": str, "conversation_id": str}`، بيرجع إجابة مهيكلة حسب Answer Schema + `_trace`

## orchestrator-api ↔ answer-validator-api
- `POST /validate_answer` — بياخد الإجابة، بيرجع valid/invalid + سبب لو فشل

## orchestrator-api ↔ ui-service
- عن طريق endpoints الـ orchestrator نفسها (`/ask`, `/documents`, إلخ)

## كل الخدمات ↔ eval-service
- Tracing تلقائي عن طريق Langfuse SDK (مش API منفصل بالضرورة)

---
**TODO للفريق**: كل owner يملى تفاصيل الـ request/response body بتاعة endpoints الخدمة بتاعته هنا بمجرد ما يتحدد.
