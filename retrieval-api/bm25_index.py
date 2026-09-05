import re
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

_chunk_store: Dict[str, Dict[str, Any]] = {}
_tokenized_corpus: List[List[str]] = []
_chunk_ids_order: List[str] = []
_bm25_index: Optional[BM25Okapi] = None



def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())

def add_chunks(chunks: List[Dict[str, Any]]) -> int:
    global _bm25_index

    for c in chunks:
        _chunk_store[c["chunk_id"]] = c
        _chunk_ids_order.append(c["chunk_id"])
        _tokenized_corpus.append(_tokenize(c["text"]))

    if _tokenized_corpus:
        _bm25_index = BM25Okapi(_tokenized_corpus)

    return len(chunks)


def bm25_search(
    query: str,
    top_k: int = 30,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if _bm25_index is None:
        return []

    tokenized_query = _tokenize(query)
    scores = _bm25_index.get_scores(tokenized_query)

    scored = list(zip(_chunk_ids_order, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for chunk_id, score in scored:
        if score <= 0:
            continue
        chunk = _chunk_store[chunk_id]

        if filters:
            doc_filter = filters.get("document_id")
            type_filter = filters.get("content_type")
            if doc_filter and chunk["document_id"] != doc_filter:
                continue
            if type_filter and chunk["content_type"] != type_filter:
                continue

        results.append({
           "chunk_id": chunk_id,
           "text": chunk["text"],
           "document_id": chunk["document_id"],
           "page": chunk["page"],
           "section": chunk["section"],
           "content_type": chunk["content_type"],
           "score": float(score),
                          })
        if len(results) >= top_k:
            break

    return results

def filter_chunks(document_id: str, page: Optional[int] = None) -> List[Dict[str, Any]]:
    results = []
    for chunk_id in _chunk_ids_order:
        chunk = _chunk_store[chunk_id]
        if chunk["document_id"] != document_id:
            continue
        if page is not None and chunk["page"] != page:
            continue
        results.append({**chunk, "score": 1.0})
    return results