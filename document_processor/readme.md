# Document Processing Service

A foundational microservice designed to ingest raw financial PDFs or images, extract high-fidelity text and table structures using **Docling** and **RapidOCR**, and return a structured payload for downstream chunking, retrieval, and RAG pipelines.

---

##  Pipeline Context

This service represents **Stage 1** of the overall end-to-end processing pipeline. It strictly handles document ingestion—it does not handle embeddings, vector stores, or retrieval.

```
PDF / Image
    │
    ▼
[ Stage 1: Document Processing ]  <-- (This Service)
    │
    ▼
[ Stage 2: Chunking ]
    │
    ▼
[ Stage 3: Embedding + BM25 Retrieval ]
    │
    ▼
[ Stage 4: Reranking ]
    │
    ▼
[ Stage 5: Agent / RAG ]
    │
    ▼
[ Stage 6: Answer Validation ]
    │
    ▼
Final Answer

```

---

##  Workflow Overview

```
Raw File (PDF/Image)
         │
         ▼
 FastAPI Endpoint (/process)
         │
         ▼
  Document Processor
         │
         ▼
  Docling + RapidOCR
         │
         ▼
 Structured Data Generation
         │
         ▼
  JSON API Response

```

---

##  Codebase Architecture

* `processor.py`: Contains core document extraction logic. Uses **Docling** with **RapidOCR** and `TableFormerMode.ACCURATE` to generate Markdown and structured document abstractions.
* `doc_processor_api.py`: Exposes a RESTful FastAPI interface for the pipeline. Accepts file uploads, temporarily stores them on disk during execution, forwards them to `processor.py`, and ensures cleanup via `finally` execution blocks.

---

##  Getting Started

### Prerequisites

Install required dependencies:

```bash
pip install fastapi uvicorn docling rapidocr_onnxruntime

```

### Running the Service

Execute the main API script directly:

```bash
python doc_processor_api.py

```

The service will host locally at:

* **API Base URL:** `[http://127.0.0.1:8000](http://127.0.0.1:8000)`
* **Swagger Documentation:** `[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)`

---

## 🔌 API Integration

Downstream services interact with the processor exclusively through HTTP requests without needing direct access to `processor.py`.

### Endpoint

`POST /process`

### Request Example (Python)

```python
import requests

url = "http://127.0.0.1:8000/process"

with open("financial_report.pdf", "rb") as f:
    response = requests.post(url, files={"file": f})

data = response.json()
print(data)

```

### Response Schema

```json
{
  "document_id": "financial_report",
  "markdown_content": "# Financial Report 2025\n\n...",
  "raw_docling_dict": {
    "pages": [],
    "tables": [],
    "structures": {}
  }
}

```

---

##  Consuming the Response

| Target Feature | Target Key | Recommended Usage |
| --- | --- | --- |
| **Text Chunking** | `markdown_content` | Ideal for section-aware, table-aware, or parent-child chunking. |
| **Structured Data** | `raw_docling_dict` | Extracts layout details, sections, pages, and precise table representations. |
