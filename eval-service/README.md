# eval-service

Evaluation & Observability service for **Project LEDGER**.
Owns: automated benchmarking against TAT-DQA, EM/F1/numerical-accuracy,
Recall@K/Precision@K scoring, Langfuse tracing, experiment comparison,
and failure analysis.

## What's here

```
eval-service/
├── app/
│   ├── main.py            FastAPI app: benchmark, failure-analysis, and comparison endpoints
│   ├── benchmark.py       Builds held-out set from raw TAT-DQA JSON, runs it, scores it
│   ├── metrics.py         EM, F1, numerical accuracy, Recall@K, Precision@K, MRR (unit tested)
│   ├── langfuse_client.py Tracing helper — real Langfuse v4 spans; no-ops if keys aren't set
│   └── schemas.py         Pydantic models mirroring the Strict Answer Schema
├── tests/test_metrics.py  Standalone tests for the scoring functions
├── requirements.txt
└── .env           Copy to .env and fill in — .env itself is gitignored
```

## Why it's structured this way

- **`metrics.py` has zero dependency on the rest of the pipeline.**
  Pure functions, unit tested (`pytest tests/` — 9 passing). This is
  what backs the Exact Match / F1 / numerical accuracy / Recall@K /
  Precision@K numbers the spec requires.
- **`benchmark.py`'s `run_benchmark` takes `call_orchestrator` and an
  optional `call_retrieval` as parameters**, so scoring logic can be
  tested with a stub independent of whether the real services are up.
- **`langfuse_client.py` wraps the real, installed Langfuse SDK (v4).**
  v4 replaced the old `.trace()`/`.span()` API with an OpenTelemetry-
  based one (`start_as_current_observation`) — this module targets
  that real API, not the older one most tutorials show. It degrades
  to a safe no-op if `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`
  aren't set.

## Setup

```bash
cd eval-service
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | (blank) | Leave blank to run with tracing off. Set both to enable real Langfuse traces. |
| `LANGFUSE_HOST` / `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` | `LANGFUSE_HOST` takes precedence. |
| `EVAL_DATA_DIR` | `./data` | Where the held-out set and run results get written locally. Gitignored — regenerated per machine, not committed. |
| `ORCHESTRATOR_URL` | `http://localhost:8000` | orchestrator-api's confirmed port. |

## Run the API

```bash
python -m uvicorn app.main:app --reload --port 8006
```
(Not port `8005` — that's answer-validator-api's default, per orchestrator-api's `config.py`.)

Interactive docs at `http://127.0.0.1:8006/docs`.

## Run the metric unit tests

```bash
python -m pytest tests/ -v
```

## Building the held-out benchmark

Once you have a copy of TAT-DQA downloaded:

```bash
curl -X POST localhost:8006/benchmark/build \
  -H "Content-Type: application/json" \
  -d '{"tatdqa_path": "/path/to/tatdqa_dataset.json", "n": 100, "seed": 42}'
```

Samples 100 questions, writes them to `./data/holdout_questions.json`.
**Note:** `build_holdout_set` reads field names (`doc`, `uid`,
`rel_paragraphs`, etc.) based on the standard TAT-DQA release shape —
verify against the actual downloaded file and adjust if it differs.

## Running the benchmark against the live pipeline

Confirmed against orchestrator-api's real code:

- `POST /ask` takes `{"question": str, "conversation_id": str}` only
  (`extra="forbid"` — no way to scope to one document; matches the
  spec's corpus-wide-by-default requirement).
- `_call_orchestrator` reuses each question's `question_id` as
  `conversation_id`, so a run can be traced back through
  orchestrator/agent logs or Langfuse later.
- The response includes `_trace.latency_ms`, which is used directly
  instead of measuring round-trip time ourselves.

```bash
curl -X POST localhost:8006/benchmark/run \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'   # smoke-test on 10 questions first
```

## Retrieval metrics (Recall@K / Precision@K)

The evaluator sends every question only to orchestrator `/ask`. When the
orchestrator forwards ranked candidates in `_trace.retrieved_candidates`,
the evaluator computes Recall@K and Precision@K from that list. If candidates
are absent, those metrics are returned as `null`; the evaluator never calls
retrieval-api directly.

## Failure analysis and experiments

- `GET /benchmark/failure-analysis/{run_id}` returns the five lowest-scoring
  cases with their evidence and error details.
- `POST /benchmark/compare` with `baseline_run_id` and `candidate_run_id`
  returns metric deltas for an experiment.

## Testing benchmark.py without a live orchestrator

```python
from app.benchmark import build_holdout_set, run_benchmark

questions = build_holdout_set("tatdqa_dataset.json", n=5)

def fake_orchestrator(question: str, question_id: str) -> dict:
    return {
        "answer_type": "direct",
        "evidence": [{"document_id": "doc_001", "page": 1}],
        "params": {"value": "placeholder"},
    }

summary = run_benchmark(questions, fake_orchestrator, k=5)
print(summary.exact_match, summary.f1)
```

## What's NOT built yet (next steps)

- `agent-service` forwards `_usage` with `llm_calls`, `input_tokens`,
  `output_tokens`, and `tokens`; benchmark summaries aggregate these into
  `total_llm_calls` and `total_tokens`.
- [ ] Orchestrator/agent-service don't create their own Langfuse spans
      internally yet — `run_benchmark` traces its own calls *to* them,
      but the steps *inside* agent-service (retrieval, reranking, tool
      calls, generation) aren't individually traced. Needs Thomas
      and/or Hassan to instrument their own code with this module (or
      their own Langfuse calls) for step-level failure analysis.
- [ ] Confirm the real TAT-DQA field names once the dataset is
      downloaded and adjust `build_holdout_set` if they differ.
