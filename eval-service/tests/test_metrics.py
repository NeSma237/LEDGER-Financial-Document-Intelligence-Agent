from app.metrics import (
    exact_match,
    f1_score,
    multi_span_f1,
    numerical_accuracy,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_exact_match_basic():
    assert exact_match("The Answer", "the answer")
    assert exact_match("$142.5M", "$142.5M")
    assert not exact_match("142.5", "142.6")


def test_f1_partial_overlap():
    score = f1_score("net income increased", "net income")
    assert 0.5 < score < 1.0


def test_f1_no_overlap():
    assert f1_score("marketing", "logistics") == 0.0


def test_numerical_accuracy_within_tolerance():
    assert numerical_accuracy(13.41, 13.4)
    assert numerical_accuracy("$142.5M", "142500000")
    assert numerical_accuracy("(1,234)", -1234)


def test_numerical_accuracy_out_of_tolerance():
    assert not numerical_accuracy(10, 13.4)


def test_multi_span_f1_order_independent():
    assert multi_span_f1(["R&D", "Marketing"], ["Marketing", "R&D"]) == 1.0


def test_multi_span_f1_partial():
    score = multi_span_f1(["Marketing", "R&D"], ["Marketing", "R&D", "Logistics"])
    assert 0.5 < score < 1.0


def test_recall_precision_at_k():
    retrieved = ["p1", "p2", "p3", "p4", "p5"]
    relevant = ["p3", "p9"]
    assert recall_at_k(retrieved, relevant, k=5) == 0.5
    assert precision_at_k(retrieved, relevant, k=5) == 0.2


def test_reciprocal_rank():
    assert reciprocal_rank(["p1", "p2", "p3"], ["p3"]) == 1 / 3
    assert reciprocal_rank(["p1", "p2"], ["p9"]) == 0.0
