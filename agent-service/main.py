from fastapi import FastAPI
from pydantic import BaseModel
from graph import build_graph
import httpx, os, time
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Agent Service")
agent = build_graph()

VALIDATOR_URL = os.getenv("VALIDATOR_URL", "http://localhost:8003")


class QuestionRequest(BaseModel):
    question: str
    conversation_id: str = "default"


@app.post("/agent/answer")
def answer_question(req: QuestionRequest):
    start = time.time()

    # 1. Agent thinking
    result = agent.invoke({
        "question": req.question,
        "conversation_id": req.conversation_id,
        "question_type": "",
        "retrieved_chunks": [],
        "evidence_sufficient": False,
        "final_answer": None,
        "retry_count": 0,
        "start_time": start
    })

    answer = result["final_answer"]
    latency = int((time.time() - start) * 1000)

    # 2. send to Validator
    try:
        val_resp = httpx.post(
            f"{VALIDATOR_URL}/validate_answer",
            json=answer,
            timeout=10
        ).json()

        validated = val_resp.get("valid", False)
        val_reason = val_resp.get("reason", "")

    except Exception:
        validated = False
        val_reason = "Validator unreachable"

    # 3. if fail validation → insufficient
    if not validated:
        answer = {
            "answer": "Insufficient evidence to answer the question.",
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {
                "reason": f"Validation failed: {val_reason}"
            }
        }

    else:
        # 4. Addd  human-readable answer
        answer_type = answer.get("answer_type")
        params = answer.get("params", {})

        if answer_type == "calculated":
            value = params.get("value")
            unit = params.get("unit", "thousand USD")

            if value is not None:
                if unit == "thousand USD":
                    answer["answer"] = f"${value / 1000:.3f} million"
                else:
                    answer["answer"] = str(value)

        elif answer_type == "direct":
            value = params.get("value")
            answer["answer"] = str(value) if value is not None else ""

        elif answer_type == "multi_span":
            answer["answer"] = str(params.get("values", []))

        elif answer_type == "insufficient_evidence":
            answer["answer"] = "Insufficient evidence to answer the question."

    # 5. backkk to Orchestrator
    return {
        **answer,
        "validated": validated,
        "_trace": {
            "conversation_id": req.conversation_id,
            "question_type_classified": result.get("question_type", "unknown"),
            "retrieval_attempts": result.get("retry_count", 0) + 1,
            "calculation_performed": answer.get("answer_type") == "calculated",
            "latency_ms": latency
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}