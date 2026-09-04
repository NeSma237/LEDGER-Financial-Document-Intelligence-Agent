import logging
from typing import Any, Dict
from pydantic import ValidationError
from schemas import (
    Evidence, DirectParams, CalculatedParams, MultiSpanParams,
    InsufficientEvidenceParams, ValidationResponse
)

logger = logging.getLogger("answer-validator")

VALID_ANSWER_TYPES = {"direct", "calculated", "multi_span", "insufficient_evidence"}

EVIDENCE_REQUIRED_TYPES = {"direct", "calculated", "multi_span"}

PARAMS_MODEL_MAP = {
    "direct": DirectParams,
    "calculated": CalculatedParams,
    "multi_span": MultiSpanParams,
    "insufficient_evidence": InsufficientEvidenceParams,
}


def validate_answer(payload: Dict[str, Any]) -> ValidationResponse:
    # 1. Check answer_type
    answer_type = payload.get("answer_type")
    if not answer_type:
        reason = "Missing required field 'answer_type'"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    if answer_type not in VALID_ANSWER_TYPES:
        reason = f"Unknown answer_type '{answer_type}'. Must be one of: {', '.join(sorted(VALID_ANSWER_TYPES))}"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 2. Check evidence field exists
    evidence_raw = payload.get("evidence")
    if evidence_raw is None:
        reason = "Missing required field 'evidence'"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    if not isinstance(evidence_raw, list):
        reason = "Field 'evidence' must be a list"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 3. Validate each evidence item
    evidence_items = []
    for i, item in enumerate(evidence_raw):
        if not isinstance(item, dict):
            reason = f"Evidence item at index {i} must be an object"
            print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
            return ValidationResponse(valid=False, reason=reason)
        try:
            evidence_items.append(Evidence(**item))
        except ValidationError as e:
            errors = e.errors()
            detail = errors[0]["msg"] if errors else str(e)
            reason = f"Malformed evidence at index {i}: {detail}"
            print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
            return ValidationResponse(valid=False, reason=reason)

    # 4. Check evidence requirement for types that need it
    if answer_type in EVIDENCE_REQUIRED_TYPES and len(evidence_items) == 0:
        reason = "Missing required evidence citation"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 5. Check params
    params_raw = payload.get("params")
    if params_raw is None:
        reason = "Missing required field 'params'"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    if not isinstance(params_raw, dict):
        reason = "Field 'params' must be an object"
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 6. Validate params with type-specific model
    params_model_cls = PARAMS_MODEL_MAP[answer_type]
    try:
        params_model_cls(**params_raw)
    except ValidationError as e:
        errors = e.errors()
        if errors:
            err = errors[0]
            field = ".".join(str(loc) for loc in err["loc"]) if err.get("loc") else "unknown"
            msg = err["msg"]
            if err["type"] == "missing":
                reason = f"Missing required key '{field}'"
            else:
                reason = f"Invalid field '{field}': {msg}"
        else:
            reason = str(e)
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 7. Success
    evidence_summary = {"document_id": evidence_items[0].document_id, "page": evidence_items[0].page} if evidence_items else {}
    print(f"[ANSWER-VALIDATOR-SUCCESS] Received and validated answer of type '{answer_type}' with evidence {evidence_summary}.")
    return ValidationResponse(valid=True, message="Answer validated successfully")
