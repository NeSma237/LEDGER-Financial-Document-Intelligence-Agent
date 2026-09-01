# Strict Answer Schema

كل إجابة من agent-service لازم تتبع الشكل ده بالظبط، والـ answer-validator-api هيرفض أي انحراف عنه.

## البنية الأساسية

```json
{
  "answer_type": "<type_name>",
  "evidence": [ { "document_id": "...", "page": 0, "section": "..." } ],
  "params": { ... }
}
```

## الأنواع الأربعة (الحد الأدنى الإجباري)

### 1. direct
لإجابة مباشرة من مستند واحد.

| Parameter | Type | Constraints |
|---|---|---|
| value | string/number | إجباري |
| evidence | array | إجباري — citation واحد على الأقل بـ document_id و page |

```json
{
  "answer_type": "direct",
  "evidence": [ { "document_id": "doc_017", "page": 1, "section": "Income Statement" } ],
  "params": { "value": "$142.5M" }
}
```

### 2. calculated
لإجابة ناتجة عن عملية حسابية (لازم تعدي على calculator tool).

| Parameter | Type | Constraints |
|---|---|---|
| value | number | إجباري — النتيجة النهائية |
| formula | string | إجباري — يوضح العملية، مثال: "(150-120)/120*100" |
| evidence | array | إجباري — citation واحد لكل operand |

```json
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "doc_041", "page": 2, "section": "Operating Expenses" },
    { "document_id": "doc_041", "page": 2, "section": "Operating Expenses" }
  ],
  "params": { "value": 13.4, "formula": "(3875-3410)/3410*100" }
}
```

### 3. multi_span
لإجابة فيها أكتر من قيمة (قائمة عناصر).

| Parameter | Type | Constraints |
|---|---|---|
| values | array of string/number | إجباري — قيمة لكل عنصر بالترتيب |
| evidence | array | إجباري — citation واحد على الأقل لكل قيمة |

```json
{
  "answer_type": "multi_span",
  "evidence": [ { "document_id": "doc_022", "page": 3, "section": "Operating Expenses" } ],
  "params": { "values": ["Marketing", "R&D", "Logistics"] }
}
```

### 4. insufficient_evidence
لما مفيش دليل كافي — ممنوع تخمين الإجابة.

| Parameter | Type | Constraints |
|---|---|---|
| reason | string | إجباري — شرح مختصر لللي مش موجود |
| evidence | array | اختياري — ممكن تكون فاضية |

```json
{
  "answer_type": "insufficient_evidence",
  "evidence": [],
  "params": { "reason": "No document in the indexed corpus reports restructuring expenses." }
}
```

> ملحوظة: أي نوع إضافي (زي comparison/ranking) لازم يتوثق هنا لو الفريق قرر يضيفه، وبنفس القاعدة: أي نوع لازم evidence.
