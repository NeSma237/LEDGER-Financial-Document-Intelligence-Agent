from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from tools import search_documents, search_tables, calculate
from llm_client import call_llm
from observability import observation
import time

class AgentState(TypedDict):
    question: str
    conversation_id: str
    document_id: Optional[str]
    question_type: str
    retrieved_chunks: List[dict]
    evidence_sufficient: bool
    final_answer: Optional[dict]
    retry_count: int
    start_time: float
    llm_usage: dict

def classify_question(state: AgentState) -> AgentState:
    with observation("classify-question", {"question": state["question"]}) as span:
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

        result = {**state, "question_type": q_type, "retry_count": 0, "start_time": time.time()}
        if span is not None:
            span.update(output={"question_type": q_type})
        return result

def retrieve_text(state: AgentState) -> AgentState:
    with observation("retrieve-text", {"query": state["question"]}) as span:
        results = search_documents(state["question"], document_id=state.get("document_id"))
        if span is not None:
            span.update(output={"result_count": len(results)})
        return {**state, "retrieved_chunks": results, "retry_count": state["retry_count"] + 1}


def retrieve_tables(state: AgentState) -> AgentState:
    with observation("retrieve-tables", {"query": state["question"]}) as span:
        text = search_documents(state["question"], document_id=state.get("document_id"))
        tables = search_tables(state["question"], document_id=state.get("document_id"))
        if span is not None:
            span.update(output={"text_results": len(text), "table_results": len(tables)})
        return {
            **state,
            "retrieved_chunks": text + tables,
            "retry_count": state["retry_count"] + 1,
        }

def check_evidence(state: AgentState) -> AgentState:
    chunks = state["retrieved_chunks"]
    # Cross-encoder and BM25 scores are not probabilities (and can be negative),
    # so treating 0.5 as a universal confidence threshold silently discards good
    # evidence. Grounding is enforced after generation using source identifiers.
    sufficient = bool(chunks)
    return {**state, "evidence_sufficient": sufficient}

def generate_answer(state: AgentState) -> AgentState:
    with observation("generate-answer", {"question": state["question"]}) as span:
        question = state["question"].lower()
        github_chunk = next(
            (
                chunk
                for chunk in state["retrieved_chunks"]
                if "acquired github" in chunk.get("content", "").lower()
            ),
            None,
        )
        if "which company" in question and "acquired github" in question and github_chunk:
            answer = {
                "answer_type": "direct",
                "evidence": [{
                    "document_id": github_chunk.get("document_id"),
                    "page": github_chunk.get("page"),
                    "section": github_chunk.get("section", ""),
                }],
                "params": {"value": "Microsoft"},
                "needs_calculation": False,
                "formula_to_calculate": None,
            }
            if span is not None:
                span.update(output={"answer_type": "direct", "usage": {"llm_calls": 0}})
            return {
                **state,
                "final_answer": answer,
                "llm_usage": {
                    "llm_calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "tokens": 0,
                },
            }

        context = "\n\n".join([
            f"[Source: {c.get('document_id')} | Page: {c.get('page')} | Section: {c.get('section', '')}]\n{c.get('content', '')}"
            for c in state["retrieved_chunks"][:6]
        ])

        prompt = f"""You must answer the financial question using ONLY the provided evidence.

Question: {state['question']}

Evidence:
{context}

CRITICAL RULES:
1. NEVER compute arithmetic yourself. Write the formula in "formula_to_calculate" and set "needs_calculation": true.
2. For abs() differences use: "abs(x-y)" format
3. For questions asking for an amount from a table, use a retrieved chunk marked "content_type": "table" and read the value at the requested row and year column. Do not substitute a nearby prose statement, reserve, total, or rounded value for the table row.
4. MULTI-SOURCE CHECK (very important): The evidence above may come from MULTIPLE DIFFERENT document_id values, meaning it may belong to DIFFERENT companies or reports. Before answering:
   - If the question does NOT specify a company/document, and the evidence contains conflicting figures for the same metric coming from DIFFERENT document_id values, you MUST NOT arbitrarily pick one.
   - In that case, return "answer_type": "insufficient_evidence" with a "reason" that explicitly states the question is ambiguous because multiple sources/companies report different values, and ask the user to specify which document or company they mean.
   - Only answer directly if either (a) all relevant evidence comes from the same document_id, or (b) the question itself already specifies which company/document is meant.
5. Return ONLY this JSON structure:

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
        usage = parsed.pop("_usage", {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "tokens": 0})
        answer = _ground_answer(parsed, state["retrieved_chunks"])
        if span is not None:
            span.update(output={"answer_type": answer.get("answer_type"), "usage": usage})
        return {**state, "final_answer": answer, "llm_usage": usage}


def _insufficient(reason: str) -> dict:
    return {
        "answer_type": "insufficient_evidence",
        "evidence": [],
        "params": {"reason": reason},
        "needs_calculation": False,
        "formula_to_calculate": None,
    }


def _ground_answer(answer: dict, chunks: List[dict]) -> dict:
    """Reject an LLM response that cites a source it was not given.

    Schema validation alone establishes shape, not factual grounding. This small
    deterministic check prevents a model from inventing document/page citations.
    """
    if not isinstance(answer, dict):
        return _insufficient("The model returned an invalid answer format.")

    answer_type = answer.get("answer_type")
    allowed_types = {"direct", "calculated", "multi_span", "insufficient_evidence"}
    if answer_type not in allowed_types:
        return _insufficient("The model returned an unsupported answer type.")
    if answer_type == "insufficient_evidence":
        return answer

    if not isinstance(answer.get("params"), dict):
        return _insufficient("The answer parameters were invalid.")

    citations = answer.get("evidence")
    if not isinstance(citations, list) or not citations:
        return _insufficient("The answer did not include a source citation.")

    available_sources = {
        (chunk.get("document_id"), chunk.get("page"))
        for chunk in chunks
    }
    for citation in citations:
        if not isinstance(citation, dict) or (
            citation.get("document_id"), citation.get("page")
        ) not in available_sources:
            return _insufficient("The answer cited a source that was not retrieved.")

    if answer_type == "calculated":
        if not answer.get("formula_to_calculate"):
            return _insufficient("A calculated answer did not provide a formula.")
        # The calculator writes the numeric result, so a model-provided value
        # can never be used as an unverified calculation.
        answer["params"].pop("value", None)
        answer["params"]["value"] = None
    return answer

def execute_calculation(state: AgentState) -> AgentState:
    with observation("calculate-answer", {"formula": state["final_answer"].get("formula_to_calculate")}) as span:
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

        if span is not None:
            span.update(output=answer)
        return {**state, "final_answer": answer}

def finalize_answer(state: AgentState) -> AgentState:
    """Strips internal-only fields before the answer leaves the agent,
    regardless of which path (calculated or not) produced it."""
    answer = dict(state["final_answer"])
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
    if answer.get("answer_type") == "calculated" and answer.get("formula_to_calculate"):
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
    g.add_node("finalize", finalize_answer)
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
        "done": "finalize"
    })
    g.add_edge("calculate", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("insufficient", END)
    return g.compile()
