from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Union


class AskRequest(BaseModel):
    question: str
    conversation_id: str = "default"


class Evidence(BaseModel):
    document_id: str
    page: int
    section: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    answer_type: str
    evidence: List[Evidence] = []
    params: Dict[str, Any] = {}
    validated: bool = False
    _trace: Optional[Dict[str, Any]] = None

    class Config:
        # Allow underscore-prefixed fields to be included in serialization
        populate_by_name = True


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int = 0
    status: str = "success"
    message: str = ""


class DocumentInfo(BaseModel):
    document_id: str
    chunks_indexed: int = 0


class DocumentsResponse(BaseModel):
    documents: List[DocumentInfo] = []
    total: int = 0


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
