import logging
from typing import Any, Dict
from pydantic import ValidationError
from schemas import (
    Evidence, DirectParams, CalculatedParams, MultiSpanParams,
    InsufficientEvidenceParams, DirectAnswer, CalculatedAnswer,
    MultiSpanAnswer, InsufficientEvidenceAnswer, ValidationResponse
)

logger = logging.getLogger("answer-validator")

VALID_ANSWER_TYPES = {"direct", "calculated", "multi_span", "insufficient_evidence"}
EVIDENCE_REQUIRED_TYPES = {"direct", "calculated", "multi_span"}

ANSWER_MODEL_MAP = {
    "direct": DirectAnswer,
    "calculated": CalculatedAnswer,
    "multi_span": MultiSpanAnswer,
    "insufficient_evidence": InsufficientEvidenceAnswer,
}


def validate_answer(payload: Dict[str, Any]) -> ValidationResponse:
    # 1. Check answer_type
    answer_type = payload.get("answer_type")
    if not answer_type:
        reason = "Missing required field 'answer_type'"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    if answer_type not in VALID_ANSWER_TYPES:
        reason = f"Unknown answer_type '{answer_type}'. Must be one of: {', '.join(sorted(VALID_ANSWER_TYPES))}"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 2. Check evidence field exists
    evidence_raw = payload.get("evidence")
    if evidence_raw is None:
        reason = "Missing required field 'evidence'"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    if not isinstance(evidence_raw, list):
        reason = "Field 'evidence' must be a list"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 3. Check params field exists
    params_raw = payload.get("params")
    if params_raw is None:
        reason = "Missing required field 'params'"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    if not isinstance(params_raw, dict):
        reason = "Field 'params' must be an object"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 4. Check for unexpected top-level keys
    extra_top_keys = set(payload.keys()) - {"answer_type", "evidence", "params"}
    if extra_top_keys:
        extra_key = sorted(extra_top_keys)[0]
        reason = f"Invalid field '{extra_key}': Extra inputs are not permitted"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 5. Strict schema validation via top-level typed model
    model_cls = ANSWER_MODEL_MAP[answer_type]
    try:
        validated = model_cls(**payload)
    except ValidationError as e:
        errors = e.errors()
        if errors:
            err = errors[0]
            loc_parts = [str(l) for l in err.get("loc", [])]
            field = ".".join(loc_parts) if loc_parts else "unknown"
            msg = err.get("msg", "")

            # Check if this error is specifically in evidence items
            if len(loc_parts) >= 2 and loc_parts[0] == "evidence":
                idx = loc_parts[1]
                reason = f"Malformed evidence at index {idx}: {msg}"
            elif err["type"] == "missing":
                # Use innermost field name for compatibility
                field_name = loc_parts[-1] if loc_parts else field
                reason = f"Missing required key '{field_name}'"
            elif "extra inputs are not permitted" in msg.lower():
                reason = f"Invalid field '{field}': Extra inputs are not permitted"
            else:
                reason = f"Invalid field '{field}': {msg}"
        else:
            reason = str(e)
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer for '{answer_type}': {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 6. Check non-empty evidence requirement for types that require evidence
    if answer_type in EVIDENCE_REQUIRED_TYPES and len(validated.evidence) == 0:
        reason = "Missing required evidence citation"
        logger.error(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        print(f"[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: {reason}")
        return ValidationResponse(valid=False, reason=reason)

    # 7. Success
    evidence_summary = {"document_id": validated.evidence[0].document_id, "page": validated.evidence[0].page} if validated.evidence else {}
    success_msg = f"[ANSWER-VALIDATOR-SUCCESS] Received and validated answer of type '{answer_type}' with evidence {evidence_summary}."
    logger.info(success_msg)
    print(success_msg)
    return ValidationResponse(valid=True, message="Answer validated successfully")
