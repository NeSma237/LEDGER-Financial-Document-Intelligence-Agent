from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional

from schemas import (
    IndexRequest,
    IndexResponse,
    SearchQueryRequest,
    FilterDocumentsRequest,
    RetrievalResponse,
    RetrievalResult,
)

from chunking import chunk_document
import vector_store
import bm25_index
from reranker import rerank


app = FastAPI(
    title="retrieval-api",
    version="0.1.0",
)


# =========================================================
# Retrieval Settings
# =========================================================

# Retrieve a large number of candidates from both methods.
OVER_RETRIEVE_K = 100

# Number of candidates passed from RRF to the CrossEncoder.
RRF_CANDIDATES = 50

# RRF constant.
RRF_K = 60


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================
# Indexing
# =========================================================

@app.post("/index", response_model=IndexResponse)
def index_document(payload: IndexRequest):

    pages_as_dicts = [
        page.model_dump()
        for page in payload.pages
    ]

    chunks = chunk_document(
        payload.document_id,
        pages_as_dicts,
    )

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No content available for indexing",
        )

    vector_store.add_chunks(chunks)
    bm25_index.add_chunks(chunks)

    return IndexResponse(
        document_id=payload.document_id,
        chunks_indexed=len(chunks),
    )


# =========================================================
# Reciprocal Rank Fusion
# =========================================================

def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    top_k: int = RRF_CANDIDATES,
) -> List[Dict[str, Any]]:
    """
    Merge Vector Search and BM25 results using
    Reciprocal Rank Fusion (RRF).

    RRF score:

        1 / (RRF_K + rank)

    A chunk that appears in both retrieval systems
    receives contributions from both rankings.
    """

    fused: Dict[str, Dict[str, Any]] = {}

    # -----------------------------------------------------
    # Vector Search
    # -----------------------------------------------------

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):
        chunk_id = result["chunk_id"]

        if chunk_id not in fused:
            fused[chunk_id] = {
                **result,
                "rrf_score": 0.0,
            }

        fused[chunk_id]["rrf_score"] += (
            1.0 / (RRF_K + rank)
        )

    # -----------------------------------------------------
    # BM25 Search
    # -----------------------------------------------------

    for rank, result in enumerate(
        bm25_results,
        start=1,
    ):
        chunk_id = result["chunk_id"]

        if chunk_id not in fused:
            fused[chunk_id] = {
                **result,
                "rrf_score": 0.0,
            }

        fused[chunk_id]["rrf_score"] += (
            1.0 / (RRF_K + rank)
        )

    # -----------------------------------------------------
    # Sort by RRF score
    # -----------------------------------------------------

    ranked = sorted(
        fused.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )

    return ranked[:top_k]


# =========================================================
# Hybrid Search
# =========================================================

def hybrid_search(
    query: str,
    top_k: int,
    content_type: Optional[str] = None,
) -> List[Dict[str, Any]]:

    filters: Dict[str, Any] = {}

    if content_type is not None:
        filters["content_type"] = content_type

    # -----------------------------------------------------
    # 1. Vector Search
    # -----------------------------------------------------

    vector_results = vector_store.vector_search(
        query=query,
        top_k=OVER_RETRIEVE_K,
        filters=filters,
    )

    # -----------------------------------------------------
    # 2. BM25 Search
    # -----------------------------------------------------

    bm25_results = bm25_index.bm25_search(
        query=query,
        top_k=OVER_RETRIEVE_K,
        filters=filters,
    )

    # -----------------------------------------------------
    # 3. RRF Fusion
    # -----------------------------------------------------

    candidates = reciprocal_rank_fusion(
        vector_results=vector_results,
        bm25_results=bm25_results,
        top_k=RRF_CANDIDATES,
    )

    if not candidates:
        return []

    # -----------------------------------------------------
    # 4. CrossEncoder Reranking
    # -----------------------------------------------------

    reranked_results = rerank(
        query=query,
        candidates=candidates,
        top_k=top_k,
    )

    return reranked_results


# =========================================================
# Convert Internal Result → API Result
# =========================================================

def to_retrieval_result(
    result: Dict[str, Any],
) -> RetrievalResult:

    return RetrievalResult(
        document_id=result["document_id"],
        page=result["page"],
        section=result.get("section"),
        content_type=result["content_type"],
        content=result["text"],
        score=float(
            result.get(
                "rerank_score",
                result.get(
                    "rrf_score",
                    result.get("score", 0.0),
                ),
            )
        ),
    )


# =========================================================
# Search Documents
# =========================================================

@app.post(
    "/search_documents",
    response_model=RetrievalResponse,
)
def search_documents(
    payload: SearchQueryRequest,
):

    results = hybrid_search(
        query=payload.query,
        top_k=payload.top_k,
        content_type="text",
    )

    return RetrievalResponse(
        results=[
            to_retrieval_result(result)
            for result in results
        ]
    )


# =========================================================
# Search Tables
# =========================================================

@app.post(
    "/search_tables",
    response_model=RetrievalResponse,
)
def search_tables(
    payload: SearchQueryRequest,
):

    results = hybrid_search(
        query=payload.query,
        top_k=payload.top_k,
        content_type="table",
    )

    return RetrievalResponse(
        results=[
            to_retrieval_result(result)
            for result in results
        ]
    )


# =========================================================
# Filter Documents
# =========================================================

@app.post(
    "/filter_documents",
    response_model=RetrievalResponse,
)
def filter_documents(
    payload: FilterDocumentsRequest,
):

    results = bm25_index.filter_chunks(
        document_id=payload.document_id,
        page=payload.page,
    )

    return RetrievalResponse(
        results=[
            RetrievalResult(
                document_id=result["document_id"],
                page=result["page"],
                section=result.get("section"),
                content_type=result["content_type"],
                content=result["text"],
                score=float(
                    result.get("score", 1.0)
                ),
            )
            for result in results
        ]
    )