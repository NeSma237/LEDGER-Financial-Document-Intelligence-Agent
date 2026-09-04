# Agent Service — AI Reasoning & Agent Engineer

## Overview

The `agent-service` is the "brain" responsible for reasoning and inference in the LEDGER system. Its role is to receive the question from the Orchestrator, classify it, call the appropriate tools, and produce a validated answer that matches the Strict Answer Schema.

---

## Component Responsibilities

| Responsibility | Details |
|---|---|
| Question classification | Determine the question type: text, table, or numerical |
| Tool invocation | Search text and tables, filtering, and calculation |
| LLM calculation restriction | Every calculation must go through the Calculator Tool |
| Answer generation | The LLM produces JSON matching the Schema |
| Answer validation | Send it to the Answer Validator before returning it |

---

## Complete Data Flow

```
Orchestrator-API
      │
      │  POST /agent/answer
      │  { "question": "...", "conversation_id": "..." }
      ▼
agent-service  ◄──────────────────────────────────────────┐
      │                                                     │
      │  1. Classifies the question (numerical / table / text) │
      │  2. Calls the Retrieval API                           │
      │  3. Sends the context to the LLM                     │
      │  4. The LLM writes only the formula                  │
      │  5. The Calculator Tool calculates                  │
      │  6. Sends the answer to the Validator                │
      │                                                     │
      ▼                                                     │
Answer Validator API                                        │
      │                                                     │
      │  { "valid": true/false, "reason": "..." }          │
      └────────────────────────────────────────────────────┘
      │
      │  Final answer
      ▼
Orchestrator-API
```

---

## File Structure

```
agent-service/
├── main.py              # FastAPI entry point + validation logic
├── graph.py             # LangGraph State Machine
├── tools.py             # The four tools
├── schemas.py           # Answer Schema with Pydantic
├── llm_client.py        # Communication with the Groq API
├── mock_retrieval.py    # Mock Server for independent testing
├── mock_validator.py    # Mock Validator for independent testing
├── requirements.txt
└── .env
```

---

## APIs for This Component

### Received From: Orchestrator

```
POST /agent/answer
```

**Request Body:**
```json
{
  "question": "How far apart were the 2019 finished-goods balances reported by CTS and Jabil?",
  "conversation_id": "conv_001"
}
```

### Sent To: Answer Validator (Before Returning)

```
POST /validate_answer
```

```json
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "cts_2019", "page": 2, "section": "Inventories" }
  ],
  "params": {
    "value": 304811.0,
    "formula": "abs(9447-314258)"
  }
}
```

### Final Response to the Orchestrator

```json
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "cts_2019_annual_report", "page": 2, "section": "Inventories" },
    { "document_id": "jabil_2019_annual_report", "page": 1, "section": "Inventories" }
  ],
  "params": {
    "value": 304811.0,
    "formula": "abs(9447-314258)"
  },
  "validated": true,
  "_trace": {
    "conversation_id": "conv_001",
    "question_type_classified": "numerical",
    "retrieval_attempts": 1,
    "calculation_performed": true,
    "latency_ms": 1340
  }
}
```

### Health Check

```
GET /health
→ { "status": "ok" }
```

---

## Requirements from the Previous Component (Retrieval API)

### Required Endpoints

**1. POST `/search_documents`**
```json
// Request
{ "query": "operating income 2020", "top_k": 10 }

// Response
{
  "results": [
    {
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content": "Operating income was $142.5M in 2020.",
      "score": 0.92,
      "content_type": "text"
    }
  ]
}
```

**2. POST `/search_tables`**
```json
// Request
{ "query": "finished goods balance 2019", "top_k": 10 }

// Response — same structure as search_documents with content_type: "table"
```

**3. POST `/filter_documents`**
```json
// Request
{ "document_id": "doc_017", "page": 2 }

// Response — same structure as search_documents
```

### Required Fields in Every Result

| Field | Type | Required? |
|---|---|---|
| `document_id` | string | ✅ Yes |
| `page` | int | ✅ Yes |
| `content` | string | ✅ Yes |
| `score` | float (0-1) | ✅ Yes |
| `section` | string | ⚠️ Send `""` if not available |
| `content_type` | `"text"` or `"table"` | ✅ Yes |

---

## LangGraph State Machine

### Nodes and Conditional Paths

```
[classify]
    │
    ├── question_type == "table" or "numerical"
    │         └──► [retrieve_tables]
    │                      │
    └── question_type == "text"        │
              └──► [retrieve_text] ◄──┘
                         │
                    [check_evidence]
                         │
              ┌──────────┼──────────┐
          sufficient   retry    insufficient
              │           │           │
         [generate]  [retrieve_text] [insufficient_node]
              │                           │
    ┌─────────┴─────────┐                END
needs_calc    no_calc
    │              │
[calculate]       END
    │
   END
```

### Supported Question Types

| Type | Keywords | Example |
|---|---|---|
| `numerical` | increase, decrease, apart, compare, percent | "How far apart were..." |
| `table` | inventory, balance, finished goods, breakdown | "What was the inventory..." |
| `text` | All other questions | "Who is the CEO of..." |

---

## The Four Tools

### 1. `search_documents(query)`
Searches text through the Retrieval API.

### 2. `search_tables(query)`
Searches tables through the Retrieval API.

### 3. `calculate(expression)`
A deterministic calculator using `ast.parse` — **without any LLM**.

```python
calculate("abs(9447-314258)")
# → {"result": 304811.0, "formula": "abs(9447-314258)", "error": null}
```

### 4. `filter_documents(metadata)`
Filters by document_id or page through the Retrieval API.

---

## LLM Calculation Restriction Rule

```
✅ Correct:
   LLM writes:  "formula_to_calculate": "abs(9447-314258)"
   Calculator calculates: result = 304811.0

❌ Wrong (Forbidden):
   LLM says: "the answer is 304811"  ← it calculates from memory
```

The LLM **writes only the formula**, and the Calculator always performs the calculation.

---

## Strict Answer Schema

### 1. direct — Direct answer from the document
```json
{
  "answer_type": "direct",
  "evidence": [{ "document_id": "doc_017", "page": 1, "section": "Income Statement" }],
  "params": { "value": "$142.5M" }
}
```

### 2. calculated — Calculated answer
```json
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "doc_041", "page": 2, "section": "Operating Expenses" },
    { "document_id": "doc_089", "page": 1, "section": "Inventories" }
  ],
  "params": {
    "value": 304811.0,
    "formula": "abs(9447-314258)"
  }
}
```

### 3. multi_span — Multi-span answer
```json
{
  "answer_type": "multi_span",
  "evidence": [{ "document_id": "doc_022", "page": 3, "section": "Operating Expenses" }],
  "params": { "values": ["Marketing", "R&D", "Logistics"] }
}
```

### 4. insufficient_evidence — Insufficient evidence
```json
{
  "answer_type": "insufficient_evidence",
  "evidence": [],
  "params": { "reason": "No document in the indexed corpus reports restructuring expenses." }
}
```

---

## Environment Setup and Running the Service

### `.env` Requirements

```dotenv
GROQ_API_KEY=your_groq_api_key
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
RETRIEVAL_URL=http://localhost:8001
VALIDATOR_URL=http://localhost:8003
```

### Install Requirements

```bash
pip install fastapi uvicorn httpx python-dotenv langgraph langchain langchain-core pydantic
```

### Run the Service Locally

```bash
# Terminal 1 - Mock Retrieval (for testing)
python mock_retrieval.py

# Terminal 2 - Mock Validator (for testing)
python mock_validator.py

# Terminal 3 - Agent Service
uvicorn main:app --port 8002 --reload
```

---

## Testing the Service

### Health Check Test
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/health" -Method GET
```

### Arithmetic Question Test
```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8002/agent/answer" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "How far apart were the 2019 finished-goods balances reported by CTS and Jabil?", "conversation_id": "test_001"}'
```

### Direct Question Test (span)
```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8002/agent/answer" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "What was the operating income in 2020?", "conversation_id": "test_002"}'
```

### Expected Result for the Arithmetic Question
```json
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "cts_2019_annual_report", "page": 2, "section": "Inventories" },
    { "document_id": "jabil_2019_annual_report", "page": 1, "section": "Inventories" }
  ],
  "params": {
    "value": 304811.0,
    "formula": "abs(9447-314258)"
  },
  "validated": true,
  "_trace": {
    "conversation_id": "test_001",
    "question_type_classified": "numerical",
    "retrieval_attempts": 1,
    "calculation_performed": true,
    "latency_ms": 1340
  }
}
```

---

## Component Status

| Component | Status |
|---|---|
| LangGraph State Machine with Conditional Branches | ✅ Complete |
| The four tools (search_documents, search_tables, calculate, filter_documents) | ✅ Complete |
| Programmatic LLM calculation restriction | ✅ Complete |
| Strict Answer Schema (4 types) | ✅ Complete |
| FastAPI Endpoint `/agent/answer` | ✅ Complete |
| Integration with Answer Validator before returning | ✅ Complete |
| Mock Servers for independent testing | ✅ Complete |
| LLM Client (Groq) | ✅ Complete |

---

## Dataset Used for Testing

File: `questions_setA_practice.json` — 100 questions from TAT-DQA

| Answer Type | Count |
|---|---|
| arithmetic | 40 |
| span | 40 |
| multi-span | 13 |
| unanswerable | 5 |
| count | 2 |

---

## Important Notes for Other Teams

- The agent **does not return an answer to the Orchestrator until it has first been validated by the Validator**
- Any answer that fails validation is automatically converted to `insufficient_evidence`
- The `_trace` is included in every response to support Langfuse in the eval-service
- The Calculator supports: `+`, `-`, `*`, `/`, `**`, `abs()`
