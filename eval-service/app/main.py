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

import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.benchmark import build_holdout_set, load_holdout_set, run_benchmark, save_holdout_set
from app.schemas import (
    BenchmarkSummary,
    ExperimentComparison,
    FailureAnalysis,
    FailureCase,
)

app = FastAPI(title="LEDGER eval-service", version="0.1.0")

DATA_DIR = Path(os.getenv("EVAL_DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
HOLDOUT_PATH = DATA_DIR / "holdout_questions.json"

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")

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


class RunBenchmarkRequest(BaseModel):
    run_id: Optional[str] = None
    k: int = 5
    limit: Optional[int] = None  # cap questions for a quick smoke-test run
    score_retrieval: bool = True  # requires candidates in the orchestrator trace


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
        score_retrieval=req.score_retrieval,
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


def _load_run(run_id: str) -> BenchmarkSummary:
    if not run_id or Path(run_id).name != run_id:
        raise HTTPException(400, "Invalid run_id")
    path = DATA_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, f"No stored run: {run_id}")
    return BenchmarkSummary.model_validate_json(path.read_text())


@app.get("/benchmark/failure-analysis/{run_id}", response_model=FailureAnalysis)
def failure_analysis(run_id: str):
    """Return the five lowest-scoring cases for reproducible investigation."""
    summary = _load_run(run_id)
    failed = [
        result for result in summary.results
        if result.error
        or result.exact_match is False
        or (result.f1 is not None and result.f1 < 1.0)
        or result.numerical_correct is False
    ]
    failed.sort(key=lambda result: (
        result.error is None,
        result.f1 if result.f1 is not None else 0.0,
        result.exact_match is True,
    ))
    cases = [
        FailureCase(
            question_id=result.question_id,
            question=result.question,
            error=result.error,
            answer_type=result.predicted_answer.answer_type if result.predicted_answer else None,
            exact_match=result.exact_match,
            f1=result.f1,
            numerical_correct=result.numerical_correct,
            evidence=result.predicted_answer.evidence if result.predicted_answer else [],
            latency_ms=result.latency_ms,
        )
        for result in failed[:5]
    ]
    return FailureAnalysis(run_id=run_id, total_failures=len(failed), cases=cases)


class CompareRunsRequest(BaseModel):
    baseline_run_id: str
    candidate_run_id: str


@app.post("/benchmark/compare", response_model=ExperimentComparison)
def compare_runs(req: CompareRunsRequest):
    """Compare two persisted runs to make benchmark experiments measurable."""
    baseline = _load_run(req.baseline_run_id)
    candidate = _load_run(req.candidate_run_id)

    def delta(candidate_value: Optional[float], baseline_value: Optional[float]) -> Optional[float]:
        if candidate_value is None or baseline_value is None:
            return None
        return candidate_value - baseline_value

    return ExperimentComparison(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        exact_match_delta=candidate.exact_match - baseline.exact_match,
        f1_delta=candidate.f1 - baseline.f1,
        numerical_accuracy_delta=candidate.numerical_accuracy - baseline.numerical_accuracy,
        recall_at_k_delta=delta(candidate.recall_at_k, baseline.recall_at_k),
        precision_at_k_delta=delta(candidate.precision_at_k, baseline.precision_at_k),
        latency_delta_ms=delta(candidate.avg_latency_ms, baseline.avg_latency_ms),
    )


@app.get("/benchmark/{run_id}", response_model=BenchmarkSummary)
def get_run(run_id: str):
    return _load_run(run_id)
