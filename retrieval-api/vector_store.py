from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_client = chromadb.PersistentClient(path="./chroma_data")
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL_NAME
)
_collection = _client.get_or_create_collection(
    name="ledger_chunks",
    embedding_function=_embedding_fn,
)

def add_chunks(chunks: List[Dict[str, Any]]) -> int:
    if not chunks:
        return 0

    _collection.add(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[{
            "document_id": c["document_id"],
            "page": c["page"],
            "section": c["section"],
            "content_type": c["content_type"],
        } for c in chunks],
    )
    return len(chunks)

def vector_search(
    query: str,
    top_k: int = 30,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    where = {k: v for k, v in (filters or {}).items() if v is not None} or None

    results = _collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where,
    )

    output = []
    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    for i in range(len(ids)):
        score = 1.0 / (1.0 + dists[i])
        output.append({
            "chunk_id": ids[i],
            "text": docs[i],
            "document_id": metas[i]["document_id"],
            "page": metas[i]["page"],
            "section": metas[i]["section"],
            "content_type": metas[i]["content_type"],
            "score": score,
        })
    return output