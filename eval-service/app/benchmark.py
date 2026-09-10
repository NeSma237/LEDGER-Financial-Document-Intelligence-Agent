"""
Held-out benchmark builder + runner for Project LEDGER.

Two separate responsibilities live here:

1. `build_holdout_set` — turn TAT-DQA's raw dataset file into a fixed,
   reproducible held-out sample of BenchmarkQuestion objects. This
   uses TAT-DQA's own JSON (questions/answers/derivations) only to
   BUILD the eval set — never as the production document
   representation, per the spec's dataset rule.

2. `run_benchmark` — send each held-out question to the orchestrator,
   score the response, and produce a BenchmarkSummary.

Nothing here assumes the other six services exist yet: `run_benchmark`
takes a `call_orchestrator` function, so you can pass a stub while
those services are being built, then swap in a real HTTP call later.
"""
from __future__ import annotations

import json
import random
import time
import uuid
from pathlib import Path
from typing import Callable, List, Optional

from app.langfuse_client import traced_run
from app.metrics import (
    exact_match,
    f1_score,
    mean,
    multi_span_f1,
    numerical_accuracy,
    precision_at_k,
    recall_at_k,
)
from app.schemas import Answer, AnswerType, BenchmarkQuestion, BenchmarkResult, BenchmarkSummary


# --------------------------------------------------------------------------
# 1. Build the held-out set from raw TAT-DQA JSON
# --------------------------------------------------------------------------

def build_holdout_set(
    tatdqa_path: str,
    n: int = 100,
    seed: int = 42,
) -> List[BenchmarkQuestion]:
    """Sample `n` questions from the flat LEDGER question-bank JSON.

    Real shape (confirmed against tatdqa_source.json / questions_setA_practice.json):
    a flat list of question objects, each with `question_text`, `question_id`,
    `ground_truth_answer`, `answer_type`, `derivation`, and a `gold_evidence`
    list whose items carry `source_page` (multiple items for cross-document
    questions).
    """
    raw = json.loads(Path(tatdqa_path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(
            f"Expected a flat JSON list of questions in {tatdqa_path}, "
            f"got {type(raw).__name__}"
        )

    pool: List[BenchmarkQuestion] = []
    skipped = []
    for row in raw:
        question_text = row.get("question_text") or row.get("original_question_text")
        question_id = row.get("question_id")
        if not question_text or not question_id:
            skipped.append(row.get("question_id", "<no id>"))
            continue

        doc_id = (
            row.get("source_doc_uid")
            or row.get("anchor_source_document")
            or row.get("source_document")
            or "unknown"
        )

        pages: list[int] = []
        for evidence in row.get("gold_evidence") or []:
            page = evidence.get("source_page")
            if isinstance(page, int):
                pages.append(page)
            elif isinstance(page, str) and page.isdigit():
                pages.append(int(page))
        gt_evidence_pages = sorted(set(pages))

        pool.append(
            BenchmarkQuestion(
                question_id=str(question_id),
                question=str(question_text),
                doc_id=str(doc_id),
                gt_answer=row.get("ground_truth_answer"),
                gt_answer_type=row.get("answer_type"),
                derivation=row.get("derivation"),
                gt_evidence_pages=gt_evidence_pages,
            )
        )

    if not pool:
        raise ValueError(
            f"Loaded {len(raw)} rows from {tatdqa_path} but extracted 0 questions "
            f"— check field names against the real file shape."
        )
    if skipped:
        print(f"[build_holdout_set] skipped {len(skipped)} rows missing question_text/question_id")

    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:n]

def save_holdout_set(questions: List[BenchmarkQuestion], out_path: str) -> None:
    Path(out_path).write_text(
        json.dumps([q.model_dump() for q in questions], indent=2)
    )


def load_holdout_set(path: str) -> List[BenchmarkQuestion]:
    raw = json.loads(Path(path).read_text())
    return [BenchmarkQuestion(**q) for q in raw]


# --------------------------------------------------------------------------
# 2. Run the benchmark against the live pipeline
# --------------------------------------------------------------------------

OrchestratorCall = Callable[[str, str], dict]
"""Signature: call_orchestrator(question, question_id) -> raw JSON answer dict.

question_id gets passed through as conversation_id — orchestrator's
AskRequest only accepts `question`/`conversation_id` (extra="forbid"),
so there's no way to scope a call to one document; the pipeline is
corpus-wide by default, which is what we want to benchmark anyway."""

def _score_one(q: BenchmarkQuestion, raw_answer: Optional[dict], latency_ms: float) -> BenchmarkResult:
    result = BenchmarkResult(
        question_id=q.question_id,
        question=q.question,
        doc_id=q.doc_id,
        latency_ms=latency_ms,
    )

    if raw_answer is None:
        result.error = "no response from orchestrator"
        result.exact_match = False
        result.f1 = 0.0
        return result

    # agent-service's real contract wraps the base answer schema with
    # `validated` (bool) and a `_trace` object — pull latency from
    # there when present, since it's the pipeline's own measurement
    # rather than our round-trip timing (which also includes network
    # overhead outside the pipeline itself).
    trace = raw_answer.get("_trace") or {}
    if trace.get("latency_ms") is not None:
        result.latency_ms = trace["latency_ms"]

    if raw_answer.get("validated") is False:
        # Validator rejected it — agent-service already downgrades this
        # to insufficient_evidence before it reaches us, but guard here
        # too in case that contract changes.
        result.error = raw_answer.get("params", {}).get("reason", "failed validation")

    try:
        answer = Answer(**{k: v for k, v in raw_answer.items() if k in ("answer_type", "evidence", "params")})
    except Exception as e:  # malformed response — treat as a scored failure, not a crash
        result.error = f"invalid answer schema: {e}"
        result.exact_match = False
        result.f1 = 0.0
        return result

    result.predicted_answer = answer

    retrieved_pages = [f"{e.document_id}:{e.page}" for e in answer.evidence]
    gt_pages = [str(p) for p in q.gt_evidence_pages]
    if gt_pages:
        result.retrieval_hit = bool(
            {item.split(":", 1)[-1] for item in retrieved_pages} & set(gt_pages)
        )

    if answer.answer_type == AnswerType.INSUFFICIENT_EVIDENCE:
        # Correct only if the ground truth genuinely has no answer.
        is_correct = q.gt_answer in (None, "", [])
        result.exact_match = is_correct
        result.f1 = 1.0 if is_correct else 0.0
        return result

    if answer.answer_type == AnswerType.CALCULATED:
        pred_value = answer.params.get("value")
        result.numerical_correct = numerical_accuracy(pred_value, q.gt_answer)
        result.exact_match = result.numerical_correct
        result.f1 = 1.0 if result.numerical_correct else 0.0
        return result


    if answer.answer_type == AnswerType.MULTI_SPAN:
        pred_values = answer.params.get("values", [])
        gt_values = q.gt_answer if isinstance(q.gt_answer, list) else [q.gt_answer]
        gt_values = [str(v) for v in gt_values]
        pred_values = [str(v) for v in pred_values]
        result.f1 = multi_span_f1(pred_values, gt_values)
        result.exact_match = set(map(str.lower, pred_values)) == set(map(str.lower, gt_values))
        return result

    # DIRECT
    pred_value = str(answer.params.get("value", ""))
    gt_value = str(q.gt_answer)
    result.exact_match = exact_match(pred_value, gt_value)
    result.f1 = f1_score(pred_value, gt_value)
    return result


def extract_retrieved_ids(raw_answer: Optional[dict]) -> List[str]:
    """Read ranked retrieval candidates forwarded by the orchestrator.

    The evaluator never calls retrieval-api directly. Candidate shapes are
    intentionally tolerant because ``_trace`` is internal observability data:
    both ``{"document_id", "page"}`` objects and ``"doc:page"`` strings are
    accepted.
    """
    if not raw_answer:
        return []
    trace = raw_answer.get("_trace") or {}
    candidates = trace.get("retrieved_candidates") or trace.get("retrieved") or []
    ids: List[str] = []
    for candidate in candidates:
        if isinstance(candidate, str):
            ids.append(candidate)
            continue
        if isinstance(candidate, dict):
            document_id = candidate.get("document_id") or candidate.get("doc_id")
            page = candidate.get("page")
            if document_id is not None and page is not None:
                ids.append(f"{document_id}:{page}")
    return ids


def run_benchmark(
    questions: List[BenchmarkQuestion],
    call_orchestrator: OrchestratorCall,
    k: int = 5,
    run_id: Optional[str] = None,
    score_retrieval: bool = True,
) -> BenchmarkSummary:
    """Run every held-out question through the pipeline and score it.

    `call_orchestrator(question, question_id)` should return the
    parsed JSON body of the orchestrator's response. Per agent-service's
    contract (confirmed with Thomas), that's the base answer schema
    (`answer_type`/`evidence`/`params`) plus `validated` (bool) and a
    `_trace` object with `latency_ms`, `question_type_classified`,
    `retrieval_attempts`, etc. There's still no token/LLM-call count in
    `_trace`, so those stay unscored until Thomas adds them — `_usage`
    is supported as an optional side-channel key in the meantime, in
    case anyone wires it up ad hoc.

    Retrieval metrics use ranked candidates forwarded in the orchestrator's
    `_trace.retrieved_candidates` field. If the orchestrator does not expose
    candidates, those metrics remain None rather than bypassing it.
    """
    run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
    results: List[BenchmarkResult] = []
    retrieved_lists, relevant_lists = [], []
    total_llm_calls, total_tokens = 0, 0

    for q in questions:
        start = time.time()
        raw = None

        with traced_run(question_id=q.question_id, question=q.question) as run:
            with run.span("call_orchestrator", input={"question": q.question, "conversation_id": q.question_id}) as sp:
                try:
                    raw = call_orchestrator(q.question, q.question_id)
                    sp.end(output=raw)
                except Exception as e:
                    print(f"[EVAL] orchestrator call failed for {q.question_id}: {e}")
                    sp.end(output={"error": str(e)})

            retrieved = extract_retrieved_ids(raw) if score_retrieval else []
            if retrieved and q.gt_evidence_pages:
                retrieved_lists.append(retrieved)
                relevant_lists.append([f"{q.doc_id}:{p}" for p in q.gt_evidence_pages])

            latency_ms = (time.time() - start) * 1000
            result = _score_one(q, raw, latency_ms)
            run.finish(output={"exact_match": result.exact_match, "f1": result.f1, "error": result.error})

        results.append(result)

        result.retrieved_ids = extract_retrieved_ids(raw) if score_retrieval else []
        if raw:
            usage = raw.get("_usage", {})
            total_llm_calls += usage.get("llm_calls", 0)
            total_tokens += usage.get("tokens", 0)

    recall = mean([recall_at_k(r, rel, k) for r, rel in zip(retrieved_lists, relevant_lists)]) if retrieved_lists else None
    precision = mean([precision_at_k(r, rel, k) for r, rel in zip(retrieved_lists, relevant_lists)]) if retrieved_lists else None

    return BenchmarkSummary(
        run_id=run_id,
        n_questions=len(results),
        exact_match=mean([1.0 if r.exact_match else 0.0 for r in results if r.exact_match is not None]),
        f1=mean([r.f1 for r in results if r.f1 is not None]),
        numerical_accuracy=mean([1.0 if r.numerical_correct else 0.0 for r in results if r.numerical_correct is not None]),
        recall_at_k=recall,
        precision_at_k=precision,
        avg_latency_ms=mean([r.latency_ms for r in results if r.latency_ms is not None]),
        total_llm_calls=total_llm_calls or None,
        total_tokens=total_tokens or None,
        failed_questions=sum(1 for r in results if r.error is not None),
        results=results,
    )