from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from tools import search_documents, search_tables, calculate
from llm_client import call_llm
import time

class AgentState(TypedDict):
    question: str
    conversation_id: str
    question_type: str
    retrieved_chunks: List[dict]
    evidence_sufficient: bool
    final_answer: Optional[dict]
    retry_count: int
    start_time: float

def classify_question(state: AgentState) -> AgentState:
    q = state["question"].lower()
    numerical_kw = ["increase", "decrease", "change", "difference",
                    "how much", "percent", "ratio", "total", "sum",
                    "apart", "compare", "more than", "less than"]
    table_kw = ["table", "breakdown", "list", "which companies",
                "inventory", "balance", "finished goods"]

    if any(k in q for k in numerical_kw):
        q_type = "numerical"
    elif any(k in q for k in table_kw):
        q_type = "table"
    else:
        q_type = "text"

    return {**state, "question_type": q_type, "retry_count": 0, "start_time": time.time()}

def retrieve_text(state: AgentState) -> AgentState:
    results = search_documents(state["question"])
    return {**state, "retrieved_chunks": results}

def retrieve_tables(state: AgentState) -> AgentState:
    text = search_documents(state["question"])
    tables = search_tables(state["question"])
    return {**state, "retrieved_chunks": text + tables}

def check_evidence(state: AgentState) -> AgentState:
    chunks = state["retrieved_chunks"]
    sufficient = len(chunks) >= 1 and any(c.get("score", 0) > 0.5 for c in chunks)
    return {**state, "evidence_sufficient": sufficient}

def generate_answer(state: AgentState) -> AgentState:
    context = "\n\n".join([
        f"[Source: {c['document_id']} | Page: {c['page']} | Section: {c['section']}]\n{c['content']}"
        for c in state["retrieved_chunks"][:5]
    ])

    prompt = f"""You must answer the financial question using ONLY the provided evidence.

Question: {state['question']}

Evidence:
{context}

CRITICAL RULES:
1. NEVER compute arithmetic yourself. Write the formula in "formula_to_calculate" and set "needs_calculation": true
2. For abs() differences use: "abs(x-y)" format
3. Return ONLY this JSON structure:

{{
  "answer_type": "direct" or "calculated" or "multi_span" or "insufficient_evidence",
  "evidence": [{{"document_id": "...", "page": 0, "section": "..."}}],
  "params": {{
    // if direct:              {{"value": "..."}}
    // if calculated:          {{"value": null, "formula": "..."}}
    // if multi_span:          {{"values": [...]}}
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

    answer.pop("needs_calculation", None)
    answer.pop("formula_to_calculate", None)
    return {**state, "final_answer": answer}

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
    g.add_node("classify", classify_question)
    g.add_node("retrieve_text", retrieve_text)
    g.add_node("retrieve_tables", retrieve_tables)
    g.add_node("check_evidence", check_evidence)
    g.add_node("generate", generate_answer)
    g.add_node("calculate", execute_calculation)
    g.add_node("insufficient", insufficient_node)

    g.set_entry_point("classify")
    g.add_conditional_edges("classify", route_by_type, {
        "retrieve_text": "retrieve_text",
        "retrieve_tables": "retrieve_tables"
    })
    g.add_edge("retrieve_text", "check_evidence")
    g.add_edge("retrieve_tables", "check_evidence")
    g.add_conditional_edges("check_evidence", route_by_evidence, {
        "generate": "generate",
        "retry": "retrieve_text",
        "insufficient": "insufficient"
    })
    g.add_conditional_edges("generate", route_after_generation, {
        "calculate": "calculate",
        "done": END
    })
    g.add_edge("calculate", END)
    g.add_edge("insufficient", END)
    return g.compile()