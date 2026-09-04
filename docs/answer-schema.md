# Strict Answer Schema

Every answer from agent-service must follow this shape exactly, and answer-validator-api will reject any deviation.

## Base Structure

```json
{
  "answer_type": "<type_name>",
  "evidence": [ { "document_id": "...", "page": 0, "section": "..." } ],
  "params": { ... }
}
```

## The Four Types (Required Minimum)

### 1. direct
A fact retrieved directly from a single document.

| Parameter | Type | Constraints |
|---|---|---|
| value | string/number | Required |
| evidence | array | Required — at least one citation with document_id and page |

```json
{
  "answer_type": "direct",
  "evidence": [ { "document_id": "doc_017", "page": 1, "section": "Income Statement" } ],
  "params": { "value": "$142.5M" }
}
```

### 2. calculated
An answer derived from an arithmetic operation (must go through the calculator tool).

| Parameter | Type | Constraints |
|---|---|---|
| value | number | Required — the final result |
| formula | string | Required — shows the operation, e.g. "(150-120)/120*100" |
| evidence | array | Required — one citation per operand |

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
An answer containing more than one value (a list of items).

| Parameter | Type | Constraints |
|---|---|---|
| values | array of string/number | Required — one value per item, in order |
| evidence | array | Required — at least one citation per value |

```json
{
  "answer_type": "multi_span",
  "evidence": [ { "document_id": "doc_022", "page": 3, "section": "Operating Expenses" } ],
  "params": { "values": ["Marketing", "R&D", "Logistics"] }
}
```

### 4. insufficient_evidence
When there isn't enough grounding — guessing the answer is not allowed.

| Parameter | Type | Constraints |
|---|---|---|
| reason | string | Required — a brief explanation of what's missing |
| evidence | array | Optional — may be empty |

```json
{
  "answer_type": "insufficient_evidence",
  "evidence": [],
  "params": { "reason": "No document in the indexed corpus reports restructuring expenses." }
}
```

> Note: Any additional type (e.g. comparison/ranking) must be documented here if the team decides to add it, following the same rule: every type requires evidence.
