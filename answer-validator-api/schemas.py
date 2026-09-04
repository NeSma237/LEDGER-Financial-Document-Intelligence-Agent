from pydantic import BaseModel, Field, ConfigDict, field_validator, StrictStr, StrictInt, StrictFloat
from typing import List, Optional, Union, Literal


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    page: StrictInt
    section: Optional[str] = None

    @field_validator("document_id")
    @classmethod
    def document_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document_id must not be empty")
        return v

    @field_validator("page")
    @classmethod
    def page_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("page must be non-negative")
        return v


class DirectParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Union[StrictStr, StrictInt, StrictFloat]

    @field_validator("value")
    @classmethod
    def value_not_empty_string(cls, v):
        if type(v) is bool:
            raise ValueError("value must not be a boolean")
        if isinstance(v, str) and not v.strip():
            raise ValueError("value must not be an empty string")
        return v


class CalculatedParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Union[StrictInt, StrictFloat]
    formula: str

    @field_validator("value")
    @classmethod
    def value_not_bool(cls, v):
        if type(v) is bool:
            raise ValueError("value must be numeric, not a boolean")
        return v

    @field_validator("formula")
    @classmethod
    def formula_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("formula must not be empty")
        return v


class MultiSpanParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: List[Union[StrictStr, StrictInt, StrictFloat]]

    @field_validator("values")
    @classmethod
    def values_not_empty(cls, v):
        if not v:
            raise ValueError("values must not be empty")
        for idx, item in enumerate(v):
            if type(item) is bool:
                raise ValueError(f"Value at index {idx} must not be a boolean")
            if isinstance(item, str) and not item.strip():
                raise ValueError(f"Value at index {idx} must not be an empty or whitespace string")
        return v


class InsufficientEvidenceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason must not be empty")
        return v


class DirectAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_type: Literal["direct"]
    evidence: List[Evidence]
    params: DirectParams


class CalculatedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_type: Literal["calculated"]
    evidence: List[Evidence]
    params: CalculatedParams


class MultiSpanAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_type: Literal["multi_span"]
    evidence: List[Evidence]
    params: MultiSpanParams


class InsufficientEvidenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_type: Literal["insufficient_evidence"]
    evidence: List[Evidence] = []
    params: InsufficientEvidenceParams


class ValidationResponse(BaseModel):
    valid: bool
    message: Optional[str] = None
    reason: Optional[str] = None
