from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict, Union


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    conversation_id: str = "default"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    page: int
    section: Optional[str] = None


class AskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    answer: str
    answer_type: str
    evidence: List[Evidence] = []
    params: Dict[str, Any] = {}
    validated: bool = False
    trace: Optional[Dict[str, Any]] = Field(default=None, alias="_trace")


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    chunks_indexed: int = 0
    status: str = "success"
    message: str = ""


class DocumentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    chunks_indexed: int = 0


class DocumentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents: List[DocumentInfo] = []
    total: int = 0


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: str
    detail: Optional[str] = None
