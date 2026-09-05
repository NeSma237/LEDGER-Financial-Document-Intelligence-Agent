from fastapi import FastAPI, HTTPException
from typing import List

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
    version="0.1.0"
)

OVER_RETRIEVE_K = 30


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================
# Index Document
# =========================================================

@app.post("/index", response_model=IndexResponse)
def index_document(payload: IndexRequest):

    pages_as_dicts = [
        page.model_dump()
        for page in payload.pages
    ]

    chunks = chunk_document(
        payload.document_id,
        pages_as_dicts
    )

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No content available for indexing"
        )

    vector_store.add_chunks(chunks)
    bm25_index.add_chunks(chunks)

    return IndexResponse(
        document_id=payload.document_id,
        chunks_indexed=len(chunks)
    )


# =========================================================
# Shared Hybrid Search Function
# =========================================================

def hybrid_search(
    query: str,
    top_k: int,
    content_type: str | None = None
) -> List[dict]:

    filters = {}

    if content_type:
        filters["content_type"] = content_type

    # 1. Chroma / Vector Search
    vector_results = vector_store.vector_search(
        query,
        top_k=OVER_RETRIEVE_K,
        filters=filters
    )

    # 2. BM25 Search
    bm25_results = bm25_index.bm25_search(
        query,
        top_k=OVER_RETRIEVE_K,
        filters=filters
    )

    # 3. Merge results
    merged = {}

    for result in vector_results + bm25_results:

        chunk_id = result["chunk_id"]

        if chunk_id not in merged:
            merged[chunk_id] = result

    candidates = list(merged.values())

    if not candidates:
        return []

    # 4. Reranking
    top_results = rerank(
        query,
        candidates,
        top_k=top_k
    )

    return top_results


# =========================================================
# 1. Search Documents
# =========================================================

@app.post(
    "/search_documents",
    response_model=RetrievalResponse
)
def search_documents(payload: SearchQueryRequest):

    results = hybrid_search(
        query=payload.query,
        top_k=payload.top_k,
        content_type="text"
    )

    return RetrievalResponse(
        results=[
            RetrievalResult(
                document_id=result["document_id"],
                page=result["page"],
                section=result.get("section"),
                content_type=result["content_type"],
                content=result["text"],
                score=result.get(
                    "rerank_score",
                    result["score"]
                )
            )
            for result in results
        ]
    )


# =========================================================
# 2. Search Tables
# =========================================================

@app.post(
    "/search_tables",
    response_model=RetrievalResponse
)
def search_tables(payload: SearchQueryRequest):

    results = hybrid_search(
        query=payload.query,
        top_k=payload.top_k,
        content_type="table"
    )

    return RetrievalResponse(
        results=[
            RetrievalResult(
                document_id=result["document_id"],
                page=result["page"],
                section=result.get("section"),
                content_type=result["content_type"],
                content=result["text"],
                score=result.get(
                    "rerank_score",
                    result["score"]
                )
            )
            for result in results
        ]
    )


# =========================================================
# 3. Filter Documents
# =========================================================

@app.post(
    "/filter_documents",
    response_model=RetrievalResponse
)
def filter_documents(payload: FilterDocumentsRequest):

    results = bm25_index.filter_chunks(
        document_id=payload.document_id,
        page=payload.page
    )

    return RetrievalResponse(
        results=[
            RetrievalResult(
                document_id=result["document_id"],
                page=result["page"],
                section=result.get("section"),
                content_type=result["content_type"],
                content=result["text"],
                score=result.get("score", 1.0)
            )
            for result in results
        ]
    )