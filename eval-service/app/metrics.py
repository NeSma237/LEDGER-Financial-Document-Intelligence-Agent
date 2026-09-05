"""
Answer-quality and retrieval-quality metrics for Project LEDGER.

Kept dependency-free (no sklearn/numpy) so this module can be unit
tested and demoed on its own before any other service exists.
"""
from __future__ import annotations

import re
import string
from typing import Iterable, List, Optional, Sequence, Union

Number = Union[int, float]


# --------------------------------------------------------------------------
# Text normalization (SQuAD-style, adapted for financial text)
# --------------------------------------------------------------------------

_ARTICLES = {"a", "an", "the"}
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_text(s: str) -> str:
    """Lowercase, strip punctuation/articles/extra whitespace.

    Keeps digits, '.', and '%' meaningful for financial answers by
    normalizing separately in `_normalize_number` instead of here.
    """
    if s is None:
        return ""
    s = str(s).lower().strip()
    s = s.translate(_PUNCT_TABLE)
    tokens = [t for t in s.split() if t not in _ARTICLES]
    return " ".join(tokens)


def _try_parse_number(s: str) -> Optional[float]:
    """Best-effort parse of a financial-looking string into a float.

    Handles things like "$142.5M", "13.4%", "(1,234)" (accounting
    negatives), "1,234.56".
    """
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        return None

    txt = s.strip()
    negative = txt.startswith("(") and txt.endswith(")")
    txt = txt.strip("()")
    txt = txt.replace(",", "").replace("$", "").replace("%", "").strip()

    multiplier = 1.0
    match = re.search(r"([\d.]+)\s*([kKmMbB])?$", txt)
    if not match:
        return None
    num_str, suffix = match.groups()
    try:
        value = float(num_str)
    except ValueError:
        return None

    if suffix:
        multiplier = {"k": 1e3, "m": 1e6, "b": 1e9}[suffix.lower()]
    value *= multiplier
    if negative:
        value = -value
    return value


# --------------------------------------------------------------------------
# Exact Match / F1  (for `direct` and `multi_span` answers)
# --------------------------------------------------------------------------

def exact_match(prediction: str, ground_truth: str) -> bool:
    """String-level exact match after normalization."""
    return normalize_text(prediction) == normalize_text(ground_truth)


def f1_score(prediction: str, ground_truth: str) -> float:
    """Token-overlap F1 between prediction and ground truth."""
    pred_tokens = normalize_text(prediction).split()
    gt_tokens = normalize_text(ground_truth).split()

    if not pred_tokens or not gt_tokens:
        return float(pred_tokens == gt_tokens)

    common: dict = {}
    for tok in pred_tokens:
        common[tok] = common.get(tok, 0) + 1

    num_same = 0
    gt_counts: dict = {}
    for tok in gt_tokens:
        gt_counts[tok] = gt_counts.get(tok, 0) + 1
    for tok, cnt in gt_counts.items():
        num_same += min(cnt, common.get(tok, 0))

    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(gt_tokens)
    return 2 * precision * recall / (precision + recall)


def multi_span_f1(predictions: Sequence[str], ground_truths: Sequence[str]) -> float:
    """Set-level F1 for multi_span answers (order-independent).

    Each side is normalized and de-duplicated, then treated as a
    bag-of-items overlap — closer to what TAT-DQA's multi-span
    scoring expects than plain string EM.
    """
    pred_set = {normalize_text(p) for p in predictions}
    gt_set = {normalize_text(g) for g in ground_truths}
    if not pred_set and not gt_set:
        return 1.0
    if not pred_set or not gt_set:
        return 0.0
    overlap = len(pred_set & gt_set)
    precision = overlap / len(pred_set)
    recall = overlap / len(gt_set)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# --------------------------------------------------------------------------
# Numerical accuracy (for `calculated` answers)
# --------------------------------------------------------------------------

def numerical_accuracy(
    predicted: Union[Number, str],
    ground_truth: Union[Number, str],
    rel_tol: float = 0.01,
    abs_tol: float = 0.01,
) -> bool:
    """Whether predicted matches ground truth within tolerance.

    Handles "$142.5M", "13.4%", "(1,234)" style strings via
    `_try_parse_number`. Default 1% relative tolerance covers
    rounding differences in derived figures; falls back to a small
    absolute tolerance for values near zero.
    """
    p = _try_parse_number(predicted) if isinstance(predicted, str) else float(predicted)
    g = _try_parse_number(ground_truth) if isinstance(ground_truth, str) else float(ground_truth)
    if p is None or g is None:
        return False
    if abs(g) < abs_tol:
        return abs(p - g) <= abs_tol
    return abs(p - g) / abs(g) <= rel_tol


# --------------------------------------------------------------------------
# Retrieval metrics
# --------------------------------------------------------------------------

def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Fraction of relevant items found within the top-k retrieved."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Fraction of the top-k retrieved that are relevant."""
    if k == 0:
        return 0.0
    relevant = set(relevant_ids)
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for r in top_k if r in relevant)
    return hits / len(top_k)


def reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: Iterable[str]) -> float:
    """1 / rank of the first relevant item; 0 if none found."""
    relevant = set(relevant_ids)
    for i, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant:
            return 1.0 / i
    return 0.0


def mean_reciprocal_rank(list_of_retrieved: Sequence[Sequence[str]], list_of_relevant: Sequence[Iterable[str]]) -> float:
    scores = [
        reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in zip(list_of_retrieved, list_of_relevant)
    ]
    return sum(scores) / len(scores) if scores else 0.0


def mean(values: Sequence[float]) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0
