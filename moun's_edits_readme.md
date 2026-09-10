This document provides comprehensive documentation of recent system-wide updates (across Graph, Orchestrator, Chunking, and Retrieval API) implemented to resolve Schema Validation issues and enhance financial data extraction accuracy, along with a complete execution guide.

---

## 🛠️ Detailed Recent Updates

### 1. Environment & LLM Client (`.env` & `llm_client.py`)
* **Changes:** 
  * Updated the Groq API key in the `.env` file.
  * Set the default model name to `llama-3.3-70b-versatile`.
* **Rationale:** 
  * Resolves Authorization issues (HTTP 401).


---

### 2. Agent Graph (`graph.py`)
* **Changes:**
  1. **Added/Updated `clear_answer_schema` & `finalize_answer`:** Sanitizes LLM output to guarantee 100% adherence to the target Schema.
  2. **Updated `insufficient_evidence` Node:** Calibrated the fallback mechanism to return strict, schema-compliant data when evidence is missing.
  3. **Added Console Context Logging:** Enables real-time Terminal logging for retrieved contexts and chunks during graph node execution.
* **Rationale:**
  * Eliminates schema validation errors caused by extraneous or non-conforming payload fields.
  * Improves visibility and observability into what the LLM ingests during reasoning and retrieval.

---

### 3. Orchestrator Service
* **Changes:**
  * Updated payload validation handling within the service logic:
    ```python
    if "params" in validation_payload and isinstance(validation_payload["params"], dict):
        # Sanitize params fields to prevent extra input leaks
    ```
* **Rationale:**
  * Resolves the `Extra inputs are not permitted` validator error and prevents internal HTTP error attributes (e.g., `status_code`, `response`) from leaking into `params`.

---

### 4. Table Chunking Strategy (`chunking.py`)
* **Changes:**
  * Refactored `table_to_text` to explicitly map column headers (such as financial years 2018/2019) to their respective row values.
* **Rationale:**
  * Prevents the LLM from misinterpreting figures across different fiscal years for the same line item, enforcing direct value-to-year association.

---

### 5. Retrieval API (`main.py`)
* **Changes:**
  * Expanded scope in `search_tables` to include adjacent explanatory text alongside table chunks, applying custom sorting:
    ```python
    results = sorted(results, key=lambda x: (x["content_type"] == "table", x.get("rerank_score", 0)), reverse=True)
    ```
* **Rationale:**
  * Ensures crucial footnotes and contextual text surrounding financial tables are not omitted, raising top-k recall quality before LLM synthesis.

---

## 🚀 How to Run

Ensure a `.env` file exists in the project root directory with the following variables:
```env
GROQ_API_KEY=gsk_your_actual_key_here
LLM_MODEL=llama-3.3-70b-versatile

Launch the backend services using the orchestration script:
Bash 
python run_services.py

Once the services are active, start the UI application:
Bash
python user_interface.py