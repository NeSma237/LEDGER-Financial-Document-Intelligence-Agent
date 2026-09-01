# doc-processor-api

## المسؤولية
تحويل PDF خام إلى تمثيل منظم: نص، جداول، عناوين، أرقام صفحات، bounding boxes.

## Framework
FastAPI + (TorchServe أو مشابه)

## قيد الموديل
لازم يستخدم موديل deep-learning-based OCR/layout حقيقي (مش استخراج نص بسيط زي PyPDF بس).

## Checklist
- [ ] اختيار موديل OCR/Layout (مثال: LayoutParser, Donut, Unstructured.io، إلخ)
- [ ] استخراج الجداول بشكل منفصل عن النص العادي
- [ ] الاحتفاظ بأرقام الصفحات والأقسام
- [ ] اختبار على عينة من TAT-DQA الحقيقية (PDFs خام، مش الـ pre-parsed JSON)

## التشغيل محليًا
```bash
# TODO
```
