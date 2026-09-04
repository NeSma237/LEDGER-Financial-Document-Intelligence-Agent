from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Union, Literal


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    page: int
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
    value: Union[str, int, float]

    @field_validator("value")
    @classmethod
    def value_not_empty_string(cls, v):
        if isinstance(v, str) and not v.strip():
            raise ValueError("value must not be an empty string")
        return v


class CalculatedParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Union[int, float]
    formula: str

    @field_validator("formula")
    @classmethod
    def formula_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("formula must not be empty")
        return v


class MultiSpanParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: List[Union[str, int, float]]

    @field_validator("values")
    @classmethod
    def values_not_empty(cls, v):
        if not v:
            raise ValueError("values must not be empty")
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


class ValidationResponse(BaseModel):
    valid: bool
    message: Optional[str] = None
    reason: Optional[str] = None
