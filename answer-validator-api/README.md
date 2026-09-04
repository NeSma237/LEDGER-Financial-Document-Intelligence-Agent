# answer-validator-api

## Responsibility
The single source of truth for answer schema correctness in LEDGER. Validates that every answer produced by `agent-service` strictly adheres to the project contract before it can be presented to the user.

## Framework & Port
* **Framework:** FastAPI + Pydantic v2
* **Default Port:** `8005`

## Endpoints
* `POST /validate_answer` — Accepts an answer payload (`answer_type`, `evidence`, `params`), strictly validates data types and citations, and returns `{"valid": bool, "message": Optional[str], "reason": Optional[str]}`. Returns HTTP 200 on success, HTTP 400 on validation failure.
* `GET /health` — Health check endpoint.

## The Four Supported Answer Types
1. `direct` — Single retrieved scalar value (`params.value`) + at least one evidence citation.
2. `calculated` — Numeric scalar value (`params.value`) + arithmetic string (`params.formula`) + operand citations.
3. `multi_span` — List of non-empty scalar values (`params.values`) + evidence citations.
4. `insufficient_evidence` — Reason explanation (`params.reason`) + optional empty citation list (`evidence: []`).

## Strict Validation Rules
* Unknown/extra root fields are forbidden and rejected.
* Unknown/extra parameter fields in `params` are forbidden and rejected.
* Unknown/extra citation fields in `evidence` are forbidden and rejected.
* Strict type enforcement: booleans are not accepted as numbers or page integers.
* Whitespace-only strings in `multi_span` values or parameters are rejected.

## Logging Format
* **Success:** `[ANSWER-VALIDATOR-SUCCESS] Received and validated answer of type '<type>' with evidence {'document_id': '...', 'page': 0}.`
* **Error:** `[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: <detailed reason>`

## Running Locally
```bash
uvicorn main:app --port 8005 --reload
```

## Running Tests
```bash
pytest tests/test_validator.py -v
```
