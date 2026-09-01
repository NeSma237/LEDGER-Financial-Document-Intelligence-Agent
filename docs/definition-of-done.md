# Definition of "Done"

- [ ] السبع خدمات شغالة سوا كسيستم واحد (Docker Compose / startup script / خطوات موثقة)
- [ ] الـ ingestion بيستخدم PDFs الخام، مش الـ pre-parsed JSON بتاع الداتاست
- [ ] Gradio UI فيها corpus-wide chat + dashboard
- [ ] Retrieval بيجمع dense search + طريقة non-vector واحدة على الأقل + reranking
- [ ] كل إجابة بتتبعت وتتحقق منها answer-validator-api بنجاح
- [ ] حالات insufficient_evidence بتتعامل صح (مش hallucination) وبتتسجل
- [ ] الـ pipeline كله متتبع في Langfuse + benchmark تلقائي على held-out subset من TAT-DQA
- [ ] تحليل فشل موثق لـ 5 أمثلة على الأقل، كل واحدة بسبب جذري محدد
- [ ] الكود على GitHub بتاريخ PRs واضح من كل الفريق
- [ ] README.md بتعليمات تشغيل واضحة
