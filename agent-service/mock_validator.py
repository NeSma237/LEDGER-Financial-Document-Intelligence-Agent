from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Mock Answer Validator")

@app.post("/validate_answer")
def validate_answer(body: dict):
    answer_type = body.get("answer_type")
    evidence = body.get("evidence", [])
    params = body.get("params", {})

    # validatoor
    if not answer_type:
        print("[ANSWER-VALIDATOR-ERROR] Missing answer_type")
        return {"valid": False, "reason": "Missing answer_type"}

    if answer_type == "calculated":
        if "formula" not in params:
            print("[ANSWER-VALIDATOR-ERROR] Invalid answer for 'calculated': Missing required key 'formula'")
            return {"valid": False, "reason": "Missing required key 'formula'"}
        if not evidence:
            print("[ANSWER-VALIDATOR-ERROR] Invalid answer. Reason: Missing required evidence citation.")
            return {"valid": False, "reason": "Missing required evidence citation"}

    if answer_type == "direct":
        if "value" not in params:
            return {"valid": False, "reason": "Missing required key 'value'"}
        if not evidence:
            return {"valid": False, "reason": "Missing required evidence citation"}

    if answer_type == "multi_span":
        if "values" not in params:
            return {"valid": False, "reason": "Missing required key 'values'"}

    print(f"[ANSWER-VALIDATOR-SUCCESS] Received and validated answer of type '{answer_type}' with evidence {evidence[0] if evidence else '{}'}")
    return {"valid": True, "message": "Answer validated successfully"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)