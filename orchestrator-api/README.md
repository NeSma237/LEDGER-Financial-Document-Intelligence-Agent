# orchestrator-api

## المسؤولية
العصب المركزي للسيستم. بيستقبل طلبات المستخدم (من ui-service)، بيوجهها للخدمات المناسبة (doc-processor, retrieval, agent)، ولما الـ agent يطلع إجابة، بيبعتها لـ answer-validator-api قبل ما ترجع للمستخدم.

## Framework
FastAPI

## Endpoints المتوقعة (تتفق عليها مع الفريق)
- `POST /ingest` — استقبال PDF جديد وتوجيهه لـ doc-processor-api
- `POST /ask` — استقبال سؤال المستخدم وتنسيق الرحلة الكاملة (retrieval → agent → validator)
- `GET /documents` — قائمة المستندات المفهرسة (للـ dashboard)

## Checklist
- [ ] تعريف الـ API contracts مع كل خدمة (راجع `docs/api-contracts.md`)
- [ ] معالجة الأخطاء لو أي خدمة تانية وقعت
- [ ] Logging لكل خطوة

## التشغيل محليًا
```bash
# TODO
```
