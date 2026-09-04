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
