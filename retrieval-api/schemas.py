from typing import Optional, List, Literal
from pydantic import BaseModel


# =========================================================
# Document Structure
# =========================================================

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


# =========================================================
# Indexing
# =========================================================

class IndexRequest(BaseModel):
    document_id: str
    pages: List[Page]


class IndexResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    status: str = "success"


# =========================================================
# Search Requests
# =========================================================

class SearchQueryRequest(BaseModel):
    query: str
    top_k: int = 10


class FilterDocumentsRequest(BaseModel):
    document_id: str
    page: Optional[int] = None


# =========================================================
# Retrieval Response
# =========================================================

class RetrievalResult(BaseModel):
    document_id: str
    page: int
    section: Optional[str] = None
    content_type: Literal["text", "table"]
    content: str
    score: float


class RetrievalResponse(BaseModel):
    results: List[RetrievalResult]