import httpx
import os
import json
# from dotenv import load_dotenv

score_threshold = 3

# load_dotenv()
GROQ_API_KEY="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"
LLM_PROVIDER="groq"
LLM_MODEL="openai/gpt-oss-120b"


def call_llm(prompt: str) -> dict:
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY", "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")

    if not api_key:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "GROQ_API_KEY is missing"},
            "needs_calculation": False,
            "formula_to_calculate": None
        }
    # for sending to GROQ
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # tells the role of the system and the message of the user
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a financial analyst."
                    "Always respond with valid JSON only."
                    "No markdown, no explanation."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "max_tokens": 1000,
        "response_format": {
            "type": "json_object"
        }
    }
    # connecting to groq with the payload and header
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        # the code and response
        print("=== GROQ RESPONSE ===")
        print("Status:", r.status_code)
        print("Body:", r.text)
        print("=====================")

        r.raise_for_status()

        data = r.json()

        if "choices" not in data:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {
                    "reason": "Groq response does not contain 'choices'",
                    "response": data
                },
                "needs_calculation": False,
                "formula_to_calculate": None
            }
        # raw is the answer only
        raw = data["choices"][0]["message"]["content"]

        try:
            # print("FROM THE FIRST CODE\n", json.loads(raw))
            return json.loads(raw)
        # checking for errors when connecting
        except json.JSONDecodeError:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {
                    "reason": "LLM returned invalid JSON",
                    "raw_response": raw
                },
                "needs_calculation": False,
                "formula_to_calculate": None
            }

    except httpx.HTTPStatusError as e:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {
                "reason": "Groq API returned an HTTP error",
                "status_code": e.response.status_code,
                "response": e.response.text
            },
            "needs_calculation": False,
            "formula_to_calculate": None
        }

    except Exception as e:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {
                "reason": f"LLM request failed: {str(e)}"
            },
            "needs_calculation": False,
            "formula_to_calculate": None
        }

# just testing it works
# call_llm("What's the sum of 10 and 11")


# ========================================================================================== tools.py

import httpx, ast, operator, os

RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://localhost:8001")

def search_documents(query: str, top_k: int = 10) -> list:
    try:
        r = httpx.post(f"{RETRIEVAL_URL}/search_documents",
                       json={"query": query, "top_k": top_k}, timeout=10)
        return r.json()["results"]
    except:
        return []

# def search_tables(query: str, top_k: int = 10) -> list:
#     try:
#         r = httpx.post(f"{RETRIEVAL_URL}/search_tables",
#                        json={"query": query, "top_k": top_k}, timeout=10)
#         return r.json()["results"]
#     except:
#         return []

# def filter_documents(metadata: dict) -> list:
#     try:
#         r = httpx.post(f"{RETRIEVAL_URL}/filter_documents",
#                        json=metadata, timeout=10)
#         return r.json()["results"]
#     except:
#         return []

def calculate(expression: str) -> dict:
    try:
        result = _safe_eval(expression)
        return {"result": round(result, 4), "formula": expression, "error": None}
    except Exception as e:
        return {"result": None, "formula": expression, "error": str(e)}

def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode='eval')
    return _eval_node(tree.body)

def _eval_node(node):
    import ast as a
    if isinstance(node, a.Constant):
        return float(node.value)
    elif isinstance(node, a.BinOp):
        ops = {
            a.Add: operator.add, a.Sub: operator.sub,
            a.Mult: operator.mul, a.Div: operator.truediv,
            a.Pow: operator.pow
        }
        return ops[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    elif isinstance(node, a.Call):
        if isinstance(node.func, a.Name) and node.func.id == 'abs':
            return abs(_eval_node(node.args[0]))
    elif isinstance(node, a.UnaryOp) and isinstance(node.op, a.USub):
        return -_eval_node(node.operand)
    raise ValueError(f"Unsupported expression: {node}")


# ========================================================================================== graph.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
# from tools import search_documents, search_tables, calculate
import time

# state for langraph (basically just persisten memory, having the following fields)
class AgentState(TypedDict):
    question: str
    conversation_id: str
    # question_type: str
    retrieved_chunks: List[dict]
    evidence_sufficient: bool
    final_answer: Optional[dict]
    retry_count: int
    start_time: float

# def classify_question(state: AgentState) -> AgentState:
#     q = state["question"].lower()
#     numerical_kw = ["increase", "decrease", "change", "difference",
#                     "how much", "percent", "ratio", "total", "sum",
#                     "apart", "compare", "more than", "less than"]
#     table_kw = ["table", "breakdown", "list", "which companies",
#                 "inventory", "balance", "finished goods"]

#     if any(k in q for k in numerical_kw):
#         q_type = "numerical"
#     elif any(k in q for k in table_kw):
#         q_type = "table"
#     else:
#         q_type = "text"

#     return {**state, "question_type": q_type, "retry_count": 0, "start_time": time.time()}


####
# def search_documents(query: str, top_k: int = 10) -> list:
#     try:
#         r = httpx.post(f"{RETRIEVAL_URL}/search_documents",
#                        json={"query": query, "top_k": top_k}, timeout=10)
#         return r.json()["results"]
#     except:
#         return []
    
# top_k = 10
####
# import json_processor

def search_documents(query):
    file_path = "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\retrieved_docs_json.json"
    with open(file_path, "r") as f:
        data = json.load(f)
    return data

def retrieve_text(state: AgentState) -> AgentState:
    results = search_documents(state["question"])
    return {**state, "retrieved_chunks": results, "retry_count": state["retry_count"] + 1}


# def retrieve_tables(state: AgentState) -> AgentState:
#     text = search_documents(state["question"])
#     tables = search_tables(state["question"])
#     return {**state, "retrieved_chunks": text + tables}


def check_evidence(state: AgentState) -> AgentState:
    chunks = state["retrieved_chunks"]
    sufficient = len(chunks) >= 1 and any(c.get("score", 0) > 0.5 for c in chunks)
    good_files = [p for p in chunks if p["score"] > score_threshold]
    return {**state, "retrieved_chunks": good_files, "evidence_sufficient": sufficient}

def generate_answer(state: AgentState) -> AgentState:
    context = "\n\n".join([
        f"[Source: {c['document_id']} | Page: {c['page']} | Section: {c['section']}]\n{c['content']}"
        for c in state["retrieved_chunks"][:5]
    ])
    # print(state["retrieved_chunks"])

    prompt = f"""You must answer the financial question using ONLY the provided evidence.

Question: {state['question']}

Evidence:
{context}

CRITICAL RULES:
1. NEVER compute arithmetic yourself. Write the formula in "formula_to_calculate" and set "needs_calculation": true
2. For abs() differences use: "abs(x-y)" format
4. Return ONLY this JSON structure:

{{
  "answer_type": {{
    "direct" if it's a single value retrieved
    "calculated" if it requires an arithmetic calculation, when seeing "total" know they are asking for sum
    "multi_span" if it's more than one value retrieved
    "insufficient_evidence" otherwise,
    }},
  "evidence": [{{"document_id": "...", "page": "...", "section": "..."}}],
  "params": {{
    ONLY copy exact wording
    the schema depends on the "answer_type" as follows
    // if direct:              {{"value": "..."}}
    // if calculated:          {{"value": null, "formula": "..."}}
    // if multi_span:          {{"values": [... , ...]}}
    // if insufficient_evidence: {{"reason": "..."}}
  }},
  "needs_calculation": true or false,
  "formula_to_calculate": "expression or null"
}}"""

    parsed = call_llm(prompt)
    return {**state, "final_answer": parsed}

def execute_calculation(state: AgentState) -> AgentState:
    answer = dict(state["final_answer"])
    formula = answer.get("formula_to_calculate")

    if formula:
        calc = calculate(formula)
        if calc["error"] is None:
            answer["params"]["value"] = calc["result"]
            answer["params"]["formula"] = calc["formula"]
        else:
            answer["answer_type"] = "insufficient_evidence"
            answer["params"] = {"reason": f"Calculation error: {calc['error']}"}

    return {**state, "final_answer": answer}

def finalize_answer(state: AgentState) -> AgentState:
    """Strips internal-only fields before the answer leaves the agent,
    regardless of which path (calculated or not) produced it."""
    answer = dict(state["final_answer"])
    answer.pop("needs_calculation", None)
    answer.pop("formula_to_calculate", None)
    print("\nFINALIZED\n", answer)
    return {**state, "final_answer": answer}

# ? when would it run
def insufficient_node(state: AgentState) -> AgentState:
    return {**state, "final_answer": {
        "answer_type": "insufficient_evidence",
        "evidence": [],
        "params": {"reason": "Could not find sufficient evidence."}
    }}

# Conditional edges
def route_by_type(state: AgentState) -> str:
    return "retrieve_tables" if state["question_type"] in ["table", "numerical"] else "retrieve_text"

def route_by_evidence(state: AgentState) -> str:
    if state["evidence_sufficient"]:
        return "generate"
    elif state["retry_count"] < 1:
        return "retry"
    return "insufficient"

def route_after_generation(state: AgentState) -> str:
    answer = state.get("final_answer", {})
    if answer.get("needs_calculation") and answer.get("formula_to_calculate"):
        return "calculate"
    return "done"

def build_graph():
    g = StateGraph(AgentState)
    # g.add_node("classify", classify_question)
    g.add_node("retrieve_text", retrieve_text)
    # g.add_node("retrieve_tables", retrieve_tables)
    g.add_node("check_evidence", check_evidence)
    g.add_node("generate", generate_answer)
    g.add_node("calculate", execute_calculation)
    g.add_node("finalize", finalize_answer)
    g.add_node("insufficient", insufficient_node)

    # g.set_entry_point("classify")
    g.set_entry_point("retrieve_text")
    # g.add_conditional_edges("classify", route_by_type, {
    #     "retrieve_text": "retrieve_text",
    #     "retrieve_tables": "retrieve_tables"
    # })
    g.add_edge("retrieve_text", "check_evidence")
    # g.add_edge("retrieve_tables", "check_evidence")
    g.add_conditional_edges("check_evidence", route_by_evidence, {
        "generate": "generate",
        "retry": "retrieve_text",
        "insufficient": "insufficient"
    })
    g.add_conditional_edges("generate", route_after_generation, {
        "calculate": "calculate",
        "done": "finalize"
    })
    g.add_edge("calculate", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("insufficient", END)
    return g.compile()


# =========================================================================================== main.py

from fastapi import FastAPI
from pydantic import BaseModel
# from graph import build_graph
import httpx, os, time
# from dotenv import load_dotenv

# load_dotenv()

app = FastAPI(title="Agent Service")
agent = build_graph()

# VALIDATOR_URL = os.getenv("VALIDATOR_URL", "http://localhost:8003")


class QuestionRequest(BaseModel):
    question: str
    conversation_id: str = "default"


# @app.post("/agent/answer")
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


@app.get("/health")
def health():
    return {"status": "ok"}

class my_question():
    question = "What was the low sale price per share for each quarters in 2018 in chronological order?"
    conversation_id = "default"

answer_question(my_question)