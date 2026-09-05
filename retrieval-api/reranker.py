from typing import List, Dict, Any
from sentence_transformers import CrossEncoder

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = CrossEncoder(RERANKER_MODEL_NAME)

def rerank(query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    pairs = [(query, c["text"]) for c in candidates]
    rerank_scores = _reranker.predict(pairs)


    for c, score in zip(candidates, rerank_scores):
        c["rerank_score"] = float(score)

    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]