import gradio as gr
import httpx

ORCHESTRATOR_URL = "http://localhost:8000"


def ask_question(question, conversation_id):
    if not question.strip():
        return "❌ please enter a question", "", ""
    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/ask",
            json={"question": question, "conversation_id": conversation_id or "ui-test"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"❌ failed to connect: {e}", "", ""

    answer = data.get("answer", "")
    answer_type = data.get("answer_type", "")
    validated = data.get("validated", False)
    evidence = data.get("evidence", [])

    evidence_text = "\n".join(
        [f"- {e.get('document_id')} | page {e.get('page')} | {e.get('section', '')}" for e in evidence]
    ) or "❌ no sources available"

    status = "✅ verified" if validated else "⚠️ not verified"
    meta = f"Type: {answer_type}   |   {status}"

    return answer, meta, evidence_text


def upload_pdf(file):
    if file is None:
        return "❌ please select a PDF file"
    try:
        with open(file.name, "rb") as f:
            resp = httpx.post(
                f"{ORCHESTRATOR_URL}/ingest",
                files={"file": (file.name, f, "application/pdf")},
                timeout=300,
            )
        resp.raise_for_status()
        data = resp.json()
        return (
            f"✅ {data.get('message')}\n"
            f"Document ID: {data.get('document_id')}\n"
            f"Chunks indexed: {data.get('chunks_indexed')}"
        )
    except Exception as e:
        return f"❌ error: {e}"


def list_documents():
    try:
        resp = httpx.get(f"{ORCHESTRATOR_URL}/documents", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        docs = data.get("documents", [])
        if not docs:
            return "❌ no documents indexed yet"
        return "\n".join([f"- {d['document_id']} ({d['chunks_indexed']} chunks)" for d in docs])
    except Exception as e:
        return f"❌ error: {e}"


with gr.Blocks(title="LEDGER - Simple Test Interface") as demo:
    gr.Markdown("# 📊 LEDGER — Simple Test Interface")

    with gr.Tab("💬 Ask a Question"):
        question_input = gr.Textbox(label="Question", placeholder="Example: What was the operating income?")
        conv_id_input = gr.Textbox(label="Conversation ID (Optional)", value="ui-test")
        ask_btn = gr.Button("Submit Question", variant="primary")
        answer_output = gr.Textbox(label="Answer", lines=3)
        meta_output = gr.Textbox(label="Details")
        evidence_output = gr.Textbox(label="Sources (Evidence)", lines=5)

        ask_btn.click(
            ask_question,
            inputs=[question_input, conv_id_input],
            outputs=[answer_output, meta_output, evidence_output],
        )

    with gr.Tab("📄 Upload Document"):
        file_input = gr.File(label="Select PDF File", file_types=[".pdf"])
        upload_btn = gr.Button("Upload and Index", variant="primary")
        upload_output = gr.Textbox(label="Result", lines=4)

        upload_btn.click(upload_pdf, inputs=[file_input], outputs=[upload_output])

    with gr.Tab("📋 Indexed Documents"):
        refresh_btn = gr.Button("Refresh List")
        docs_output = gr.Textbox(label="Documents", lines=10)

        refresh_btn.click(list_documents, inputs=[], outputs=[docs_output])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)