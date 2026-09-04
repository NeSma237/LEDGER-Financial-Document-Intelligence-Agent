"""
Shared data models for eval-service.

These mirror the "Strict Answer Schema" from the project spec so the
evaluator can parse whatever the orchestrator/agent returns without
needing to import code from other services.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AnswerType(str, Enum):
    DIRECT = "direct"
    CALCULATED = "calculated"
    MULTI_SPAN = "multi_span"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Evidence(BaseModel):
    document_id: str
    page: int
    section: Optional[str] = None


class Answer(BaseModel):
    """A parsed answer coming back from the orchestrator/agent."""
    answer_type: AnswerType
    evidence: List[Evidence] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkQuestion(BaseModel):
    """One held-out TAT-DQA question used for evaluation."""
    question_id: str
    question: str
    doc_id: str
    # Ground truth as given by TAT-DQA: usually a string, a list of
    # strings (multi-span), or a number (derivation-based questions).
    gt_answer: Union[str, float, List[Union[str, float]]]
    gt_answer_type: Optional[str] = None  # span / arithmetic / multi-span / count, per TAT-DQA
    derivation: Optional[str] = None  # TAT-DQA's arithmetic expression, if present
    gt_evidence_pages: List[int] = Field(default_factory=list)


class BenchmarkResult(BaseModel):
    """One scored row: question + system prediction + computed metrics."""
    question_id: str
    question: str
    doc_id: str
    predicted_answer: Optional[Answer] = None
    latency_ms: Optional[float] = None
    exact_match: Optional[bool] = None
    f1: Optional[float] = None
    numerical_correct: Optional[bool] = None
    retrieval_hit: Optional[bool] = None  # was a gt evidence page among retrieved pages
    error: Optional[str] = None


class BenchmarkSummary(BaseModel):
    run_id: str
    n_questions: int
    exact_match: float
    f1: float
    numerical_accuracy: float
    recall_at_k: Optional[float] = None
    precision_at_k: Optional[float] = None
    mrr: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    total_llm_calls: Optional[int] = None
    total_tokens: Optional[int] = None
    approx_cost_usd: Optional[float] = None
    results: List[BenchmarkResult] = Field(default_factory=list)
