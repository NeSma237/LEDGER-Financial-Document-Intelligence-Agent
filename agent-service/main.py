from fastapi import FastAPI
from pydantic import BaseModel
from graph import build_graph
import time
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Agent Service")
agent = build_graph()

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
        "start_time": start,
        "llm_usage": {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "tokens": 0}
    })

    answer = result["final_answer"]
    latency = int((time.time() - start) * 1000)

    # The orchestrator is the single validation boundary. Validating here as
    # well duplicates a network call, increases latency, and can turn a good
    # answer into a false failure when the validator is briefly unavailable.
    answer_type = answer.get("answer_type")
    params = answer.get("params", {})
    if answer_type == "calculated":
        answer["answer"] = str(params.get("value", ""))
    elif answer_type == "direct":
        answer["answer"] = str(params.get("value", ""))
    elif answer_type == "multi_span":
        answer["answer"] = ", ".join(str(value) for value in params.get("values", []))
    else:
        answer["answer"] = "Insufficient evidence to answer the question."

    return {
        **answer,
        "_trace": {
            "conversation_id": req.conversation_id,
            "question_type_classified": result.get("question_type", "unknown"),
            "retrieval_attempts": result.get("retry_count", 0) + 1,
            "calculation_performed": answer_type == "calculated",
            "latency_ms": latency,
        },
        "_usage": result.get(
            "llm_usage",
            {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "tokens": 0},
        ),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
