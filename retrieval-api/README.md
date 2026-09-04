# retrieval-api

## Responsibility
Indexes extracted content and provides semantic (dense) search + non-vector search (BM25/metadata) + reranking.

## Framework
FastAPI + Chroma (vector DB) + sentence-transformers (embeddings + cross-encoder reranker) + rank-bm25

## Requirements
- [x] Smart chunking (section-aware / table-aware) — not naive fixed-size
- [x] Metadata preserved on every chunk: document_id, page, section, content_type
- [x] Dense (embedding) search + one non-vector search method (BM25)
- [x] Over-retrieve then rerank (top-30 → reranker → top-k)
- [x] Reranking value verified with actual before/after scores, not assumed

## Endpoints
- `POST /index` — indexes a document's pages/sections into both the vector store and BM25 index
- `POST /search_documents` — hybrid search restricted to text sections
- `POST /search_tables` — hybrid search restricted to table sections
- `POST /filter_documents` — direct lookup by document_id (and optional page), no ranking
- `GET /health` — health check

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Interactive API docs available at `http://localhost:8000/docs` once running.

### Testing with sample data
A ready-to-run test script (`test_retrieval.py`) with fake sample documents (`sample_data.py`) is included for local testing without depending on doc-processor-api's real output. Run the server first, then in a separate terminal:

```bash
python test_retrieval.py
```
