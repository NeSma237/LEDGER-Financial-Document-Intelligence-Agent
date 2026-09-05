from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from validator import validate_answer
from schemas import ValidationResponse

app = FastAPI(title="Answer Validator API", version="1.0.0")


@app.post("/validate_answer", response_model=ValidationResponse)
async def validate_answer_endpoint(request: Request):
    try:
        payload = await request.json()
    except Exception:
        print("[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: Request body is not valid JSON")
        return JSONResponse(
            status_code=400,
            content={"valid": False, "reason": "Request body is not valid JSON"}
        )

    if not isinstance(payload, dict):
        print("[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: Request body must be a JSON object")
        return JSONResponse(
            status_code=400,
            content={"valid": False, "reason": "Request body must be a JSON object"}
        )

    result = validate_answer(payload)

    if not result.valid:
        return JSONResponse(
            status_code=400,
            content=result.model_dump(exclude_none=True)
        )

    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
