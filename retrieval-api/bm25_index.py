import pickle
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi

# =========================================================
# Persistence
# =========================================================
# نفس فكرة chroma_data بتاعة vector_store.py: بنحفظ الـ index على الديسك
# عشان لو الـ service اتعمله restart (سواء في الإنتاج، أو وقت bulk indexing
# طويل اتقطع في النص) الداتا متضيعش. من غير كده كان كل حاجة بتتصفر لإنها
# كانت متخزنة في متغيرات بايثون عادية (RAM) بس.

BM25_DATA_DIR = Path("./bm25_data")
BM25_STORE_FILE = BM25_DATA_DIR / "bm25_store.pkl"

_chunk_store: Dict[str, Dict[str, Any]] = {}
_tokenized_corpus: List[List[str]] = []
_chunk_ids_order: List[str] = []
_bm25_index: Optional[BM25Okapi] = None


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _rebuild_bm25_index() -> None:
    global _bm25_index
    _bm25_index = BM25Okapi(_tokenized_corpus) if _tokenized_corpus else None


def _save_to_disk() -> None:
    BM25_DATA_DIR.mkdir(parents=True, exist_ok=True)
    # ملف مؤقت الأول، وبعدين استبدال الملف الأصلي دفعة واحدة (atomic rename)
    # عشان لو البروسيس اتقفل أثناء الكتابة، الملف القديم يفضل سليم بدل ما
    # يتلخبط نص كتابة.
    tmp_file = BM25_STORE_FILE.with_suffix(".pkl.tmp")
    with open(tmp_file, "wb") as f:
        pickle.dump(
            {
                "chunk_store": _chunk_store,
                "tokenized_corpus": _tokenized_corpus,
                "chunk_ids_order": _chunk_ids_order,
            },
            f,
        )
    tmp_file.replace(BM25_STORE_FILE)


def _load_from_disk() -> None:
    global _chunk_store, _tokenized_corpus, _chunk_ids_order

    if not BM25_STORE_FILE.exists():
        return

    try:
        with open(BM25_STORE_FILE, "rb") as f:
            data = pickle.load(f)
        _chunk_store = data.get("chunk_store", {})
        _tokenized_corpus = data.get("tokenized_corpus", [])
        _chunk_ids_order = data.get("chunk_ids_order", [])
        _rebuild_bm25_index()
    except (pickle.UnpicklingError, EOFError, KeyError) as e:
        # ملف تالف (زي لو البروسيس اتقفل أثناء الكتابة قبل ما نستخدم
        # الـ atomic rename) — بنبدأ بـ index فاضي بدل ما نكرش السيرفر كله
        print(f"⚠️  bm25_index: couldn't load {BM25_STORE_FILE} ({e}), starting empty")
        _chunk_store, _tokenized_corpus, _chunk_ids_order = {}, [], []


def reset_index() -> None:
    """بتمسح الـ index كله من الذاكرة ومن الديسك. مفيدة في الاختبارات فقط."""
    global _chunk_store, _tokenized_corpus, _chunk_ids_order, _bm25_index
    _chunk_store, _tokenized_corpus, _chunk_ids_order = {}, [], []
    _bm25_index = None
    if BM25_STORE_FILE.exists():
        BM25_STORE_FILE.unlink()


# أول ما الموديول ده يتحمّل (يعني أول ما main.py يعمل import bm25_index)
# بنحاول نرجّع أي داتا كانت متخزنة من قبل على الديسك.
_load_from_disk()


# =========================================================
# Public API (نفس الأسماء والتوقيعات القديمة تمامًا — main.py مش محتاج
# يتغير فيه حرف واحد)
# =========================================================

def add_chunks(chunks: List[Dict[str, Any]]) -> int:
    for c in chunks:
        _chunk_store[c["chunk_id"]] = c
        _chunk_ids_order.append(c["chunk_id"])
        _tokenized_corpus.append(_tokenize(c["text"]))

    _rebuild_bm25_index()
    _save_to_disk()

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