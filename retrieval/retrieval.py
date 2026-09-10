from typing import Optional, List, Literal
from pydantic import BaseModel
import json
from pathlib import Path

class TableContent(BaseModel):
    rows: List[List[str]]

class Section(BaseModel):
    section_title: Optional[str] = None
    content_type: Literal["text", "table"]

    text: Optional[str] = None
    table: Optional[TableContent] = None

    bounding_box: Optional[List[float]] = None


class Page(BaseModel):
    page_number: int
    sections: List[Section]


class IndexRequest(BaseModel):
    document_id: str
    pages: List[Page]


class IndexResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    status: str = "success"


class SearchQueryRequest(BaseModel):
    query: str
    top_k: int = 10


class FilterDocumentsRequest(BaseModel):
    document_id: str
    page: Optional[int] = None

class RetrievalResult(BaseModel):
    document_id: str
    page: int
    section: Optional[str] = None
    content_type: Literal["text", "table"]
    content: str
    score: float

# THE OUTPUT OF THE RETRIEVAL HERE!!!!!!
class RetrievalResponse(BaseModel):
    results: List[RetrievalResult]


# =========================================================================== mian.py
from fastapi import FastAPI, HTTPException
from typing import List

# from chunking import chunk_document
import vector_store
import bm25_index
# from reranker import rerank


app = FastAPI(
    title="retrieval-api",
    version="0.1.0"
)

OVER_RETRIEVE_K = 600


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================
# Index Document
# =========================================================

# @app.post("/index", response_model=IndexResponse)
# def index_document(payload: IndexRequest):

#     pages_as_dicts = [
#         page.model_dump()
#         for page in payload.pages
#     ]

#     chunks = chunk_document(
#         payload.document_id,
#         pages_as_dicts
#     )

#     if not chunks:
#         raise HTTPException(
#             status_code=400,
#             detail="No content available for indexing"
#         )

#     vector_store.add_chunks(chunks)
#     bm25_index.add_chunks(chunks)

#     return IndexResponse(
#         document_id=payload.document_id,
#         chunks_indexed=len(chunks)
#     )


# =========================================================
# Shared Hybrid Search Function
# =========================================================

def hybrid_search(query: str, top_k: int, content_type: str | None = None) -> List[dict]:

    filters = {}

    # /document_search makes it "text"
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

        chunk_id = result["document_id"]

        if chunk_id not in merged:
            merged[chunk_id] = result

    candidates = list(merged.values())

    #this code is for debugging, uncomment this to see candidates before rerank
    # for index, candidate in enumerate(candidates):
    #     print(f"id, {candidate["document_id"]}, score: {candidate["score"]}")
    #     if index == 50:
    #         break

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

# @app.post(
#     "/search_tables",
#     response_model=RetrievalResponse
# )
# def search_tables(payload: SearchQueryRequest):

#     results = hybrid_search(
#         query=payload.query,
#         top_k=payload.top_k,
#         content_type="table"
#     )

#     return RetrievalResponse(
#         results=[
#             RetrievalResult(
#                 document_id=result["document_id"],
#                 page=result["page"],
#                 section=result.get("section"),
#                 content_type=result["content_type"],
#                 content=result["text"],
#                 score=result.get(
#                     "rerank_score",
#                     result["score"]
#                 )
#             )
#             for result in results
#         ]
#     )


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

# ============================================================================================ reranker.py
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = CrossEncoder(RERANKER_MODEL_NAME)

def rerank(query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    pairs = [(query, c["text"]) for c in candidates]
    rerank_scores = _reranker.predict(pairs)


    for c, score in zip(candidates, rerank_scores):
        c["rerank_score"] = float(score)

    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]

# ============================================================================================== schemas


# ===================================================================================================== chuncking
# """
# Chunking Logic
# ==============
#     chunk_id, document_id, page, section, content_type, text
# """
# from typing import List, Dict, Any

# MAX_CHARS_PER_TEXT_CHUNK = 800  # approx. 1-2 paragraphs, or ~150 words, or ~800 characters. This is a good size for semantic search embeddings.


# def table_to_text(table_rows: List[List[str]]) -> str:

#     lines = []
#     for row in table_rows:
#         if not row:
#             continue
#         if len(row) == 1:
#             lines.append(row[0])
#         else:
#             # first column is treated as the row label, remaining columns
#             # (e.g. one per year/period) are all preserved instead of only the second
#             label = row[0]
#             values = " | ".join(row[1:])
#             lines.append(f"{label}: {values}")
#     return " | ".join(lines)


# def with_section_context(section_title: str, piece: str) -> str:

#     if not section_title or piece.strip() == section_title.strip():
#         return piece
#     return f"{section_title} — {piece}"


# def split_long_text(text: str, max_chars: int = MAX_CHARS_PER_TEXT_CHUNK) -> List[str]:

#     if len(text) <= max_chars:
#         return [text]

#     sentences = text.replace("\n", " ").split(". ")
#     chunks: List[str] = []
#     current = ""
#     for sentence in sentences:
#         candidate = f"{current}. {sentence}" if current else sentence
#         if len(candidate) > max_chars and current:
#             chunks.append(current.strip())
#             current = sentence
#         else:
#             current = candidate
#     if current:
#         chunks.append(current.strip())
#     return chunks if chunks else [text]


# def chunk_document(document_id: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

#     chunks: List[Dict[str, Any]] = []

#     for page in pages:
#         page_number = page["page_number"]
#         for section_idx, section in enumerate(page.get("sections", [])):
#             section_title = section.get("section_title") or f"section_{section_idx}"
#             content_type = section["content_type"]

#             if content_type == "table" and section.get("table"):
#                 # the table is treated as a single chunk, but we convert it to text for embedding purposes
#                 raw_text = table_to_text(section["table"]["rows"])
#                 text = with_section_context(section_title, raw_text)
#                 chunk_id = f"{document_id}_p{page_number}_s{section_idx}_table"
#                 chunks.append({
#                     "chunk_id": chunk_id,
#                     "document_id": document_id,
#                     "page": page_number,
#                     "section": section_title,
#                     "content_type": "table",
#                     "text": text,
#                 })

#             elif content_type == "text" and section.get("text"):
#                 # the text can be split if it's long, but each part will inherit the same section metadata
#                 pieces = split_long_text(section["text"])
#                 for piece_idx, piece in enumerate(pieces):
#                     text = with_section_context(section_title, piece)
#                     chunk_id = f"{document_id}_p{page_number}_s{section_idx}_t{piece_idx}"
#                     chunks.append({
#                         "chunk_id": chunk_id,
#                         "document_id": document_id,
#                         "page": page_number,
#                         "section": section_title,
#                         "content_type": "text",
#                         "text": text,
#                     })

# ===================================================================================================== 


# from tqdm import tqdm

# def load_your_jsons(file_path):
#     with open(file_path, "r", encoding="utf-8") as f:
#         return json.load(f)

# def flush_batch(chunks) -> int:
#     if not chunks:
#         return 0
#     vector_store.add_chunks(chunks)
#     bm25_index.add_chunks(chunks)
#     return len(chunks)

# def ingest_your_files(file_path):
#     loaded_jsons_to_lists = load_your_jsons(file_path)
#     return flush_batch(loaded_jsons_to_lists)

# def ingestion_pipeline(processed_files_path, registry_path):
#     processed_jsons_path = Path(processed_files_path)  # Fixed Path initialization
#     registry_path = Path(registry_path)

#     if registry_path.exists():
#         with open(registry_path, "r", encoding="utf-8") as f:
#             try:
#                 ingested_ids = set(json.load(f))
#             except json.JSONDecodeError:
#                 ingested_ids = set()
#     else:
#         ingested_ids = set()

#     # Pre-filter uningested files to accurately size the tqdm progress bar
#     all_files = list(processed_jsons_path.glob("*.json"))
#     files_to_process = [f for f in all_files if f.stem not in ingested_ids]

#     if not files_to_process:
#         print("No new files to ingest.")
#         return

#     len_of_flushed = 0
#     newly_ingested_count = 0

#     # Wrap the loop with tqdm for progress tracking
#     pbar = tqdm(files_to_process, desc="Ingesting Documents", unit="file")
    
#     for file_path in pbar:
#         doc_id = file_path.stem

#         # Update progress bar description with current file ID
#         pbar.set_postfix({"file": doc_id, "total_chunks": len_of_flushed})

#         # Ingest file
#         chunks_added = ingest_your_files(file_path)
#         len_of_flushed += chunks_added
#         newly_ingested_count += 1

#         ingested_ids.add(doc_id)

#     # Save updated IDs back to registry file
#     with open(registry_path, "w", encoding="utf-8") as f:
#         json.dump(list(ingested_ids), f, indent=2)

#     print(f"\nFinished ingesting {len_of_flushed} chunks from {newly_ingested_count} new file(s).")

# processed_files_path = r"C:\Users\Lenovo\Desktop\MIA\doc_intel\docling_processed_json"
# registry_path = r"C:\Users\Lenovo\Desktop\MIA\doc_intel\ingested_ids.json"
# ingestion_pipeline(processed_files_path, registry_path)
# uncomment this when you have new files



# now run the search documents code
class custom_search_query_request():
    query = "What is the average  Total equity  for fiscal years 2015 to 2019?"
    top_k = 100

response = search_documents(custom_search_query_request)
response = response.results # list of RetrievalResults
answer_as_list = []
for result in response:
    document_id = result.document_id
    page = result.page
    section = result.section
    content_type = result.content_type
    content = result.content
    score = result.score
    answer_as_dict = {
        "document_id": document_id,
        "page": page,
        "section": section,
        "content_type": content_type,
        "content": content,
        "score": score,
    }
    answer_as_list.append(answer_as_dict)

with open("retrieved_docs_json.json", "w") as f:
    json.dump(answer_as_list, f, indent=2)

# print(answer_as_list)
# the output is now a list of dicts, structured as the following
# document_id
# page
# section
# content_type
# content
# score
for iteration in answer_as_list:
    print(f"doc id: {iteration["document_id"]}, score: {iteration["score"]}")