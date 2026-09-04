from pydantic import BaseModel
from typing import Literal, List, Optional, Any

class Evidence(BaseModel):
    document_id: str
    page: int
    section: Optional[str] = ""

class AnswerResponse(BaseModel):
    answer_type: Literal["direct", "calculated", "multi_span", "insufficient_evidence"]
    evidence: List[Evidence]
    params: dict
    validated: Optional[bool] = None
    _trace: Optional[dict] = None