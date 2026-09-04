"""
eval-service — Evaluation & Observability API for Project LEDGER.

Endpoints:
    GET  /health
    POST /benchmark/build   -> sample a held-out set from raw TAT-DQA JSON, save it
    POST /benchmark/run     -> run the held-out set through the orchestrator, return metrics
    GET  /benchmark/{run_id} -> fetch a previously stored run's results

Run with:
    uvicorn app.main:app --reload --port 8005
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


def _call_orchestrator(question: str, doc_id: str) -> dict:
    """Default orchestrator caller — POSTs to orchestrator-api's /ask.

    Adjust the payload/path once the Leader/Orchestration Engineer
    finalizes the orchestrator's actual request contract.
    """
    resp = httpx.post(
        f"{ORCHESTRATOR_URL}/ask",
        json={"question": question, "doc_scope": None},  # corpus-wide by default, per spec
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


class RunBenchmarkRequest(BaseModel):
    run_id: Optional[str] = None
    k: int = 5
    limit: Optional[int] = None  # cap questions for a quick smoke-test run


@app.post("/benchmark/run", response_model=BenchmarkSummary)
def benchmark_run(req: RunBenchmarkRequest):
    if not HOLDOUT_PATH.exists():
        raise HTTPException(400, "No held-out set found — call /benchmark/build first")
    questions = load_holdout_set(str(HOLDOUT_PATH))
    if req.limit:
        questions = questions[: req.limit]

    summary = run_benchmark(questions, _call_orchestrator, k=req.k, run_id=req.run_id)

    out_path = DATA_DIR / f"{summary.run_id}.json"
    out_path.write_text(summary.model_dump_json(indent=2))

    print(
        f"[EVAL-SERVICE] run={summary.run_id} n={summary.n_questions} "
        f"EM={summary.exact_match:.3f} F1={summary.f1:.3f} "
        f"NumAcc={summary.numerical_accuracy:.3f}"
    )
    return summary


@app.get("/benchmark/{run_id}", response_model=BenchmarkSummary)
def get_run(run_id: str):
    path = DATA_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(404, f"No stored run: {run_id}")
    return json.loads(path.read_text())
