"""
eval-service — Evaluation & Observability API for Project LEDGER.

Endpoints:
    GET  /health
    POST /benchmark/build   -> sample a held-out set from raw TAT-DQA JSON, save it
    POST /benchmark/run     -> run the held-out set through the orchestrator, return metrics
    GET  /benchmark/{run_id} -> fetch a previously stored run's results

Run with:
    uvicorn app.main:app --reload --port 8006
    # NOTE: not 8005 — that's answer-validator-api's default port per
    # orchestrator-api's config.py, and it'll fight this service for it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.benchmark import build_holdout_set, load_holdout_set, run_benchmark, save_holdout_set
from app.schemas import BenchmarkSummary

app = FastAPI(title="LEDGER eval-service", version="0.1.0")

DATA_DIR = Path(os.getenv("EVAL_DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
HOLDOUT_PATH = DATA_DIR / "holdout_questions.json"

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")

# Only used for the retrieval-quality track (Recall@K/Precision@K), which
# the spec treats as its own metric separate from the answer benchmark —
# it's not part of asking a question through the pipeline, so calling
# retrieval-api directly for this doesn't break "only talk to the
# orchestrator" for actually answering questions.
RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://localhost:8002")


@app.get("/health")
def health():
    return {"status": "ok"}


class BuildHoldoutRequest(BaseModel):
    tatdqa_path: str
    n: int = 100
    seed: int = 42


@app.post("/benchmark/build")
def benchmark_build(req: BuildHoldoutRequest):
    """Sample and persist the held-out benchmark set."""
    if not Path(req.tatdqa_path).exists():
        raise HTTPException(404, f"TAT-DQA file not found: {req.tatdqa_path}")
    questions = build_holdout_set(req.tatdqa_path, n=req.n, seed=req.seed)
    save_holdout_set(questions, str(HOLDOUT_PATH))
    return {"n_questions": len(questions), "saved_to": str(HOLDOUT_PATH)}


def _call_orchestrator(question: str, question_id: str) -> dict:
    """Calls orchestrator-api's POST /ask — the only door we're allowed
    to knock on for actually answering a question. Everything else
    (agent-service, retrieval-api, answer-validator-api) is orchestrator's
    problem to route to, not ours.

    orchestrator's AskRequest schema only accepts `question` and
    `conversation_id` (extra fields are rejected outright — it's built
    with extra="forbid"), so there's no way to scope a question to a
    specific document even if we wanted to. That's fine — the system
    is corpus-wide by default per the spec, which is what we're
    benchmarking anyway.

    We reuse our own question_id as the conversation_id so that if
    anyone goes digging through orchestrator/agent logs or a Langfuse
    trace later, they can match it back to this exact benchmark row.
    """
    resp = httpx.post(
        f"{ORCHESTRATOR_URL}/ask",
        json={"question": question, "conversation_id": question_id},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


def _call_retrieval(question: str, top_k: int) -> list[str]:
    """Calls retrieval-api's /search_documents directly to get the ranked
    candidate list for the retrieval-quality metric track. Returns a
    list of "document_id:page" strings in ranked order — that's what
    metrics.recall_at_k/precision_at_k compare against ground-truth pages.

    This deliberately bypasses orchestrator. It's the one place that's
    allowed to, since Recall@K/Precision@K measure retrieval on its own,
    not the answer that comes out the other end of the full pipeline.
    """
    resp = httpx.post(
        f"{RETRIEVAL_URL}/search_documents",
        json={"query": question, "top_k": top_k},
        timeout=30.0,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [f"{r['document_id']}:{r['page']}" for r in results]


class RunBenchmarkRequest(BaseModel):
    run_id: Optional[str] = None
    k: int = 5
    limit: Optional[int] = None  # cap questions for a quick smoke-test run
    score_retrieval: bool = True  # set False to skip the extra retrieval-api calls


@app.post("/benchmark/run", response_model=BenchmarkSummary)
def benchmark_run(req: RunBenchmarkRequest):
    if not HOLDOUT_PATH.exists():
        raise HTTPException(400, "No held-out set found — call /benchmark/build first")
    questions = load_holdout_set(str(HOLDOUT_PATH))
    if req.limit:
        questions = questions[: req.limit]

    summary = run_benchmark(
        questions,
        _call_orchestrator,
        k=req.k,
        run_id=req.run_id,
        call_retrieval=_call_retrieval if req.score_retrieval else None,
    )

    out_path = DATA_DIR / f"{summary.run_id}.json"
    out_path.write_text(summary.model_dump_json(indent=2))

    print(
        f"[EVAL-SERVICE] run={summary.run_id} n={summary.n_questions} "
        f"EM={summary.exact_match:.3f} F1={summary.f1:.3f} "
        f"NumAcc={summary.numerical_accuracy:.3f}"
        + (f" Recall@{req.k}={summary.recall_at_k:.3f}" if summary.recall_at_k is not None else "")
    )
    return summary


@app.get("/benchmark/{run_id}", response_model=BenchmarkSummary)
def get_run(run_id: str):
    path = DATA_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, f"No stored run: {run_id}")
    return json.loads(path.read_text())
