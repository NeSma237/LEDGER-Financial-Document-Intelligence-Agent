import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from services import ServiceError

client = TestClient(app)


def _valid_agent_response():
    return {
        "answer": "$142.5M",
        "answer_type": "direct",
        "evidence": [{"document_id": "doc_017", "page": 1, "section": "Income Statement"}],
        "params": {"value": "$142.5M"},
        "validated": True,
        "_trace": {"conversation_id": "test", "latency_ms": 500}
    }


def _valid_validator_response():
    return {"valid": True, "message": "Answer validated successfully"}


def _invalid_validator_response():
    return {"valid": False, "reason": "Missing required key 'formula'"}


class TestAskEndpoint:
    @patch("main.call_validator", new_callable=AsyncMock)
    @patch("main.call_agent", new_callable=AsyncMock)
    def test_successful_ask(self, mock_agent, mock_validator):
        mock_agent.return_value = _valid_agent_response()
        mock_validator.return_value = _valid_validator_response()

        resp = client.post("/ask", json={"question": "What was the operating income?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["validated"] is True
        assert data["answer_type"] == "direct"
        assert data["answer"] == "$142.5M"

    @patch("main.call_validator", new_callable=AsyncMock)
    @patch("main.call_agent", new_callable=AsyncMock)
    def test_validator_rejects_answer(self, mock_agent, mock_validator):
        mock_agent.return_value = _valid_agent_response()
        mock_validator.return_value = _invalid_validator_response()

        resp = client.post("/ask", json={"question": "What was the operating income?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["validated"] is False
        assert data["answer_type"] == "insufficient_evidence"
        assert "Validation failed" in data["params"]["reason"]

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_agent_timeout(self, mock_agent):
        mock_agent.side_effect = ServiceError("agent-service", "Request timed out", 504)

        resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 504
        assert "error" in resp.json()

    @patch("main.call_validator", new_callable=AsyncMock)
    @patch("main.call_agent", new_callable=AsyncMock)
    def test_validator_timeout(self, mock_agent, mock_validator):
        mock_agent.return_value = _valid_agent_response()
        mock_validator.side_effect = ServiceError("answer-validator-api", "Request timed out", 504)

        resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 504
        assert "error" in resp.json()

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_agent_unavailable(self, mock_agent):
        mock_agent.side_effect = ServiceError("agent-service", "Service unavailable", 503)

        resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 503

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_agent_returns_malformed_response(self, mock_agent):
        mock_agent.return_value = {"some": "garbage"}

        resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 502


class TestValidationBypassAndIntegrity:
    @patch("main.call_validator", new_callable=AsyncMock)
    @patch("main.call_agent", new_callable=AsyncMock)
    def test_agent_with_unexpected_field_is_rejected(self, mock_agent, mock_validator):
        # Agent attempts to inject an unexpected key
        mock_agent.return_value = {
            "answer": "$142.5M",
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_017", "page": 1, "section": "Income"}],
            "params": {"value": "$142.5M"},
            "unexpected": "bad",
            "_trace": {"secret": "internal"}
        }
        # Validator rejects due to unexpected field
        mock_validator.return_value = {
            "valid": False,
            "reason": "Invalid field 'unexpected': Extra inputs are not permitted"
        }

        resp = client.post("/ask", json={"question": "Revenue?"})
        assert resp.status_code == 200
        data = resp.json()

        # Must not be accepted as successful answer
        assert data["validated"] is False
        assert data["answer_type"] == "insufficient_evidence"
        assert "unexpected" in data["params"]["reason"]
        # Injected key must never leak into final response
        assert "unexpected" not in data

        # Verify that call_validator actually received the unexpected key
        sent_payload = mock_validator.call_args[0][0]
        assert "unexpected" in sent_payload


class TestIngestionPipeline:
    @patch("main.call_retrieval_index", new_callable=AsyncMock)
    @patch("main.call_doc_processor", new_callable=AsyncMock)
    def test_ingest_success_with_docling_dict(self, mock_processor, mock_retrieval):
        # Realistic Docling structure output from doc processor
        mock_processor.return_value = {
            "document_id": "test_report.pdf",
            "raw_docling_dict": {
                "body": {"children": [{"$ref": "#/texts/0"}]},
                "texts": [{
                    "content_layer": "body",
                    "text": "Net income was 50 million.",
                    "prov": [{"page_no": 1}]
                }]
            }
        }
        mock_retrieval.return_value = {"chunks_indexed": 3}

        resp = client.post(
            "/ingest",
            files={"file": ("test_report.pdf", b"%PDF-1.4 dummy", "application/pdf")}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["chunks_indexed"] == 3
        assert data["document_id"] == "test_report.pdf"

        # Verify retrieval index was called with converted pages
        retrieval_call = mock_retrieval.call_args[0]
        assert retrieval_call[0] == "test_report.pdf"
        pages = retrieval_call[1]
        assert len(pages) == 1
        assert pages[0]["page_number"] == 1
        assert pages[0]["sections"][0]["text"] == "Net income was 50 million."

    @patch("main.call_doc_processor", new_callable=AsyncMock)
    def test_ingest_unconvertible_processor_output_rejected(self, mock_processor):
        # Doc processor returned empty or invalid docling dict
        mock_processor.return_value = {
            "document_id": "empty.pdf",
            "raw_docling_dict": {"body": {"children": []}, "texts": []}
        }

        resp = client.post(
            "/ingest",
            files={"file": ("empty.pdf", b"%PDF-1.4 empty", "application/pdf")}
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "Document conversion failed" in data["error"]

    @patch("main.call_retrieval_index", new_callable=AsyncMock)
    @patch("main.call_doc_processor", new_callable=AsyncMock)
    def test_ingest_retrieval_failure(self, mock_processor, mock_retrieval):
        mock_processor.return_value = {
            "document_id": "report.pdf",
            "raw_docling_dict": {
                "body": {"children": [{"$ref": "#/texts/0"}]},
                "texts": [{
                    "content_layer": "body",
                    "text": "Valid text.",
                    "prov": [{"page_no": 1}]
                }]
            }
        }
        mock_retrieval.side_effect = ServiceError("retrieval-api", "Vector DB down", 503)

        resp = client.post(
            "/ingest",
            files={"file": ("report.pdf", b"%PDF-1.4 data", "application/pdf")}
        )
        assert resp.status_code == 503
        assert "Retrieval indexing error" in resp.json()["error"]

    @patch("main.call_retrieval_index", new_callable=AsyncMock)
    @patch("main.call_doc_processor", new_callable=AsyncMock)
    def test_ingest_zero_chunks_indexed_rejected(self, mock_processor, mock_retrieval):
        mock_processor.return_value = {
            "document_id": "report.pdf",
            "raw_docling_dict": {
                "body": {"children": [{"$ref": "#/texts/0"}]},
                "texts": [{
                    "content_layer": "body",
                    "text": "Valid text.",
                    "prov": [{"page_no": 1}]
                }]
            }
        }
        mock_retrieval.return_value = {"chunks_indexed": 0}

        resp = client.post(
            "/ingest",
            files={"file": ("report.pdf", b"%PDF-1.4 data", "application/pdf")}
        )
        assert resp.status_code == 422
        assert "zero chunks" in resp.json()["error"].lower()


class TestDownstreamFailures:
    @patch("main.call_agent", new_callable=AsyncMock)
    def test_agent_http_500(self, mock_agent):
        mock_agent.side_effect = ServiceError("agent-service", "Internal Error", 500)
        resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 500

    @patch("main.call_validator", new_callable=AsyncMock)
    @patch("main.call_agent", new_callable=AsyncMock)
    def test_validator_http_500(self, mock_agent, mock_validator):
        mock_agent.return_value = _valid_agent_response()
        mock_validator.side_effect = ServiceError("answer-validator-api", "Internal Error", 500)
        resp = client.post("/ask", json={"question": "test"})
        assert resp.status_code == 500


class TestHealthEndpoint:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestDocumentsEndpoint:
    def test_documents_initially_empty(self):
        resp = client.get("/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data
        assert "total" in data
