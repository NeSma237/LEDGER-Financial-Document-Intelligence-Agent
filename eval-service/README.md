# eval-service

Evaluation & Observability service for **Project LEDGER**.
Owns: automated benchmarking against TAT-DQA, EM/F1/numerical-accuracy
and Recall@K/Precision@K scoring, Langfuse tracing hooks, and failure
analysis support.

## What's here

```
eval-service/
├── app/
│   ├── main.py            FastAPI app: /benchmark/build, /benchmark/run, /benchmark/{id}
│   ├── benchmark.py       Builds held-out set from raw TAT-DQA JSON, runs it, scores it
│   ├── metrics.py         EM, F1, numerical accuracy, Recall@K, Precision@K, MRR (unit tested)
│   ├── langfuse_client.py Tracing helper — no-ops safely if Langfuse isn't configured yet
│   └── schemas.py         Pydantic models mirroring the Strict Answer Schema
├── requirements.txt
└── .env
```

## Why it's structured this way

Nothing else on the team is built yet, so this is deliberately split so
each piece can be exercised independently as teammates' services come
online:

- **`metrics.py` has zero dependency on the rest of the pipeline.**
  It's pure functions you can unit test right now (`pytest tests/` —
  already passing). This is what you'll demo first and what backs the
  Exact Match / F1 / numerical accuracy / Recall@K / Precision@K
  numbers the spec requires.
- **`benchmark.py`'s `run_benchmark` takes a `call_orchestrator`
  function as a parameter.** Until orchestrator-api exists, you can
  pass a stub (see below) and get a fully working, scored benchmark
  run on fake data — useful for testing your own scoring logic and
  for showing "the eval harness works" independent of whether the
  rest of the team has shipped anything.
- **`langfuse_client.py` degrades to a no-op tracer** if
  `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` aren't set, so the
  service runs today and just starts actually sending traces once you
  (or a teammate) wires Langfuse in.

## Setup

```bash
cd eval-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Langfuse keys inside your .env
```

## Run the API

```bash
uvicorn app.main:app --reload --port 8005
```

## Building the held-out benchmark

Once you have a copy of TAT-DQA downloaded:

```bash
curl -X POST localhost:8005/benchmark/build \
  -H "Content-Type: application/json" \
  -d '{"tatdqa_path": "/path/to/tatdqa_dataset.json", "n": 100, "seed": 42}'
```

This samples 100 questions and writes them to `./data/holdout_questions.json`.
**Note:** `build_holdout_set` in `app/benchmark.py` reads field names
(`doc`, `uid`, `rel_paragraphs`, etc.) based on the standard TAT-DQA
release shape — check the actual downloaded file's keys and adjust
that function if your copy differs.

## Running the benchmark against the live pipeline

Once orchestrator-api exists and exposes a `POST /ask` endpoint (see
`_call_orchestrator` in `app/main.py` — update the path/payload to match
whatever the Leader/Orchestration Engineer actually builds):

```bash
curl -X POST localhost:8005/benchmark/run \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'   # smoke-test on 10 questions first
```

## Testing benchmark.py before orchestrator-api exists

```python
from app.benchmark import build_holdout_set, run_benchmark

questions = build_holdout_set("tatdqa_dataset.json", n=5)

def fake_orchestrator(question: str, doc_id: str) -> dict:
    # stand-in until orchestrator-api is live
    return {
        "answer_type": "direct",
        "evidence": [{"document_id": doc_id, "page": 1}],
        "params": {"value": "placeholder"},
    }

summary = run_benchmark(questions, fake_orchestrator, k=5)
print(summary.exact_match, summary.f1)
```

## Retrieval metrics (Recall@K / Precision@K)

These only get computed if the orchestrator's response JSON includes
a `_retrieved_ids` side-channel key (ranked list of page/chunk ids
that were retrieved before reranking/generation). Ask the Retrieval
Engineer to pass this through, or have the orchestrator forward
whatever `retrieval-api` returns.

## What's NOT built yet (next steps)

- [ ] Wire `langfuse_client.traced_run` into the orchestrator/agent so
      spans actually get created for retrieval / reranking / tool
      calls / generation / validation (needs coordination — this
      module can be imported by other services too).
- [ ] Confirm the real TAT-DQA field names once the dataset is
      downloaded and adjust `build_holdout_set` accordingly.
- [ ] Confirm orchestrator-api's real request/response contract and
      update `_call_orchestrator` in `main.py`.
- [ ] Add a `/benchmark/experiment` endpoint (or a small script) that
      runs two pipeline variants back-to-back and diffs their metrics
      — this is what "Experiments" in the spec is asking for.
- [ ] Failure analysis: once a real benchmark run exists, pull the 5
      worst-scoring rows from a `BenchmarkSummary.results` list and
      inspect their Langfuse traces to root-cause each one.
