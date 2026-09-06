# If the orchestrator is unreachable, every call falls back to small mock response

import os
import json
import time
import uuid
from datetime import datetime

import gradio as gr
import requests


### Config ###

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 30))
INGEST_TIMEOUT = int(os.environ.get("INGEST_TIMEOUT", 120))


# swap for a real eval-service/Langfuse call once one exists.
RECENT_QUERIES = []  # [{question, answer_type, latency_ms, validated, timestamp}]



### Backend calls ###

# check if orchestrator is up
def check_health():
    try:
        resp = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") == "ok"
    except requests.exceptions.RequestException:
        return False

# ask the orchestrator
def call_ask_question(question: str, conversation_id: str) -> dict:
    try:
        resp = requests.post(
            f"{ORCHESTRATOR_URL}/ask",
            json={"question": question, "conversation_id": conversation_id},
            timeout=REQUEST_TIMEOUT,
        )

        # error handling
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            return {
                "answer_type": "API returned error",
                "evidence": [],
                "params": {
                    "reason": data.get("detail", data.get("error", "Backend error"))
                },
                "_backend_error": True,
            }
        return data
    except requests.exceptions.RequestException:
        return {
                "answer_type": "Didn't connect to orchestrator",
                "evidence": [],
                "params": {
                    "reason": data.get("detail", data.get("error", "Backend error"))
                },
                "_backend_error": True,
            }


def call_get_documents() -> dict:
    """/documents {documents, total}."""
    try:
        resp = requests.get(f"{ORCHESTRATOR_URL}/documents", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        return _mock_documents_response()


def call_ingest_document(file_path: str) -> dict:
    if not file_path:
        return {"status": "error", "message": "No file selected."}

    filename = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            resp = requests.post(
                f"{ORCHESTRATOR_URL}/ingest", files=files, timeout=INGEST_TIMEOUT
            )
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            return {
                "status": "error",
                "message": data.get("detail", data.get("error", "Unknown error")),
                "document_id": data.get("document_id"),
            }
        return {
            "status": "success",
            "document_id": data.get("document_id"),
            "chunks_indexed": data.get("chunks_indexed"),
            "message": data.get("message", "Document ingested."),
        }
    except requests.exceptions.RequestException:
        return _mock_ingest_response(filename)




#### Mock data (when orchestrator is unreachable) ###

def _mock_documents_response() -> dict:
    documents = [
        {"document_id": "doc_017", "chunks_indexed": 24},
        {"document_id": "doc_041", "chunks_indexed": 18},
        {"document_id": "doc_022", "chunks_indexed": 31},
    ]
    return {"documents": documents, "total": len(documents)}


def _mock_ingest_response(filename: str) -> dict:
    fake_id = f"doc_mock_{abs(hash(filename)) % 1000}"
    return {
        "status": "success",
        "document_id": fake_id,
        "chunks_indexed": 15,
        "message": f"(demo mode) '{filename}' would be ingested once the orchestrator is reachable.",
    }



### Formatting ###


def extract_answer_text(data: dict) -> str:
    params = data.get("params", {}) or {}
    answer_type = data.get("answer_type")

    if answer_type == "direct":
        return str(params.get("value", "_(no value returned)_"))
    
    if answer_type == "calculated":
        value = params.get("value", "_(no value returned)_")
        formula = params.get("formula")
        return f"{value}\nFormula: {formula})" if formula else str(value)
    
    if answer_type == "multi_span":
        values = params.get("values", [])
        return ", ".join(str(v) for v in values) if values else "_(no values returned)_"
    
    if answer_type == "insufficient_evidence":
        return params.get("reason", "Insufficient evidence to answer the question.")
    
    return "_(agent returned no answer)_"


def is_validated(data: dict) -> bool:
    return data.get("validated")


def build_evidence_body(data: dict) -> str:
    answer_type = data.get("answer_type", "unknown")
    validated_badge = "✅ validated" if data.get("validated", False) else "⚠️ validation failed"

    lines = [
        f"- **Answer type:** `{answer_type}`",
        f"- **Status:** {validated_badge}",
    ]
    if answer_type == "calculated":
        formula = data.get("params", {}).get("formula", "unknown")
        lines.append(f"- **Formula:** {formula}")

    lines.append("- **Sources:**")
    evidence = data.get("evidence", [])
    if not evidence:
        lines.append("  - _No evidence returned._")
    else:
        for e in evidence:
            doc = e.get("document_id", "unknown")
            page = e.get("page", "?")
            section = e.get("section", "no section")
            lines.append(f"  - 📄 **{doc}**, page {page}, _{section}_")

    # if data.get("_backend_error"):
    #     lines.append("")
    #     lines.append("🔴 *A downstream service returned an error -- see message for detail.*")

    return "\n".join(lines)


def build_debug_json(data: dict) -> str:
    """Raw JSON for the collapsible debug/trace accordion."""
    return json.dumps(data, indent=2, default=str)




### Gradio callback functions ###


def compute_dashboard():
    data = call_get_documents()
    total_docs = data.get("total", len(data.get("documents", [])))
    total_chunks = sum(d.get("chunks_indexed", 0) for d in data.get("documents", []))

    stats_md = (
        f"### Corpus Overview\n"
        f"- **Indexed documents:** {total_docs}\n"
        f"- **Total chunks indexed:** {total_chunks}\n\n"
    )
    recent_rows = [
        [q["timestamp"], q["question"], q["answer_type"],
         "✅" if q["validated"] else "⚠️", f"{q['latency_ms']} ms"]
        for q in RECENT_QUERIES
    ]
    return stats_md, recent_rows


def chat_respond(message, history, conversation_id):
    if not message or not message.strip():
        stats_md, recent_rows = compute_dashboard()
        return history, "", gr.update(), gr.update(), gr.update(), stats_md, recent_rows

    start = time.time()
    data = call_ask_question(message, conversation_id)
    latency_ms = round((time.time() - start) * 1000)

    RECENT_QUERIES.insert(0, {
        "question": message,
        "answer_type": data.get("answer_type", "unknown"),
        "latency_ms": latency_ms,
        "validated": is_validated(data),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    })
    del RECENT_QUERIES[20:]

    answer_text = extract_answer_text(data)
    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": answer_text},
    ]

    evidence_body = build_evidence_body(data)
    debug_json = build_debug_json(data)
    stats_md, recent_rows = compute_dashboard()  # to refresh it automatically

    return history, "", evidence_body, evidence_body, debug_json, stats_md, recent_rows


def refresh_documents():
    data = call_get_documents()
    docs = data.get("documents", [])
    return [[d.get("document_id"), d.get("chunks_indexed", 0)] for d in docs]


def refresh_connection_banner():
    if check_health():
        return f"🟢 **Connected** to orchestrator at `{ORCHESTRATOR_URL}`"
    return f"🟡 **Demo mode**: orchestrator at `{ORCHESTRATOR_URL}` is unreachable, showing mock data."


def handle_ingest(file_path):
    if not file_path:
        status = "⚠️ Please select a PDF file first."
    else:
        result = call_ingest_document(file_path)
        if result["status"] == "success":
            status = (
                f"✅ **{result.get('document_id')}** ingested — "
                f"{result.get('chunks_indexed')} chunks added to the corpus.\n\n"
                f"{result.get('message', '')}"
            )
        else:
            status = f"🔴 Ingestion failed: {result.get('message')}"

    doc_rows = refresh_documents()
    stats_md, recent_rows = compute_dashboard()
    return status, doc_rows, stats_md, recent_rows




### Gradio layout ###


with gr.Blocks(title="Project LEDGER") as demo:
    conversation_id_state = gr.State(value=lambda: str(uuid.uuid4()))

    gr.Markdown("# 📊 Project LEDGER — Financial Document Intelligence Agent")
    connection_banner = gr.Markdown()

    with gr.Tabs():
        # Chat tab
        with gr.Tab("💬 Chat"):
            with gr.Row():
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(label="LEDGER", height=480)
                    with gr.Row():
                        question_box = gr.Textbox(
                            placeholder="Ask a question across the entire indexed corpus...",
                            show_label=False,
                            scale=4,
                        )
                        ask_btn = gr.Button("Ask", variant="primary", scale=1)

                with gr.Column(scale=1):
                    gr.Markdown("### 📎 Answer Evidence")
                    evidence_panel = gr.Markdown("_Ask a question to see its cited sources here._")
                    with gr.Accordion("🔍 Raw response (debug / trace)", open=False):
                        debug_box = gr.Code(language="json", label=None)

        # Documents tab
        with gr.Tab("📁 Documents"):
            gr.Markdown(
                "### 📎 Last Answer Evidence\n"
                "_Citations from your most recent chat question"
            )
            doc_tab_evidence = gr.Markdown("_No question asked yet._")

            gr.Markdown("---")
            gr.Markdown(
                "### 📤 Upload Document\n"
                "Adds a new PDF to the existing corpus -- it doesn't replace or "
                "clear anything already indexed."
            )
            upload_file = gr.File(label="Select PDF", file_types=[".pdf"], type="filepath")
            ingest_btn = gr.Button("📥 Ingest into corpus", variant="primary")
            ingest_status = gr.Markdown()

            gr.Markdown("---")
            gr.Markdown("### 🗂️ Indexed Documents")
            doc_refresh_btn = gr.Button("Refresh document list")
            doc_table = gr.Dataframe(
                headers=["document_id", "chunks_indexed"],
                interactive=False,
            )

        # Dashboard tab 
        with gr.Tab("📈 Dashboard"):
            gr.Markdown(
                "Corpus-level stats and recent query performance."
            )
            dash_refresh_btn = gr.Button("Refresh dashboard")
            dash_stats = gr.Markdown()
            gr.Markdown("### Recent Queries")
            dash_recent = gr.Dataframe(
                headers=["time", "question", "answer_type", "validated", "latency"],
                interactive=False,
            )


    ### events ###
    
    
    chat_outputs = [chatbot, question_box, evidence_panel, doc_tab_evidence, debug_box,
                     dash_stats, dash_recent]
    ask_btn.click(chat_respond, [question_box, chatbot, conversation_id_state], chat_outputs)
    question_box.submit(chat_respond, [question_box, chatbot, conversation_id_state], chat_outputs)

    doc_refresh_btn.click(refresh_documents, outputs=doc_table)
    ingest_btn.click(
        handle_ingest,
        inputs=upload_file,
        outputs=[ingest_status, doc_table, dash_stats, dash_recent],
    )
    dash_refresh_btn.click(compute_dashboard, outputs=[dash_stats, dash_recent])

    demo.load(refresh_connection_banner, outputs=connection_banner)
    demo.load(refresh_documents, outputs=doc_table)
    demo.load(compute_dashboard, outputs=[dash_stats, dash_recent])


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
