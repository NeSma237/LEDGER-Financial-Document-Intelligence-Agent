# orchestrator-api

## Responsibility
The central nervous system of the LEDGER platform. It receives requests from `ui-service`, routes document ingestion through `doc-processor-api` and `retrieval-api`, and coordinates question answering across `agent-service` and `answer-validator-api`.

## Framework & Port
* **Framework:** FastAPI
* **Default Port:** `8000`

## Endpoints
* `POST /ask` — Receives `{"question": str, "conversation_id": str}`, queries the agent, strictly validates the answer via `answer-validator-api`, and returns `AskResponse`. Unvalidated or rejected answers never reach the UI as successful answers.
* `POST /ingest` — Uploads PDF (`multipart/form-data`), processes with IBM Docling via `doc-processor-api`, adapts the output structure, and indexes chunks in `retrieval-api`. Returns `IngestResponse`.
* `GET /documents` — Lists ingested documents and total indexed chunks (`DocumentsResponse`).
* `GET /health` — Health check endpoint.

## Environment Variables
* `AGENT_SERVICE_URL` (default: `http://localhost:8003`)
* `VALIDATOR_SERVICE_URL` (default: `http://localhost:8005`)
* `DOC_PROCESSOR_URL` (default: `http://localhost:8001`)
* `RETRIEVAL_SERVICE_URL` (default: `http://localhost:8002`)
* `REQUEST_TIMEOUT` (default: `30`)
* `ORCHESTRATOR_PORT` (default: `8000`)

## Running Locally
```bash
uvicorn main:app --port 8000 --reload
```

## Running Tests
```bash
pytest tests/test_orchestrator.py tests/test_e2e_integration.py -v
```
