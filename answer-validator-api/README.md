# answer-validator-api

## المسؤولية
المصدر الوحيد للحقيقة بخصوص شكل الإجابة الصحيحة. بيستقبل JSON ويتحقق إنه متوافق تمامًا مع الـ schema.

## Framework
FastAPI أو Flask

## Endpoint
`POST /validate_answer`

## الأنواع الأربعة المطلوبة (راجع docs/answer-schema.md للتفاصيل الكاملة)
1. `direct` — قيمة واحدة + evidence
2. `calculated` — قيمة + formula + evidence لكل operand
3. `multi_span` — عدة قيم + evidence
4. `insufficient_evidence` — لما مفيش دليل كافي

## Logging المطلوب
- نجاح: `[ANSWER-VALIDATOR-SUCCESS] Received and validated answer of type '<type>' with evidence {...}`
- فشل: `[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: <السبب بالتفصيل>`

## التشغيل محليًا
```bash
# TODO
```
