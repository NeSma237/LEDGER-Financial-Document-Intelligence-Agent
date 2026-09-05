import pytest
import subprocess
import time
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Add orchestrator-api to sys.path
orch_dir = Path(__file__).resolve().parent.parent
if str(orch_dir) not in sys.path:
    sys.path.insert(0, str(orch_dir))

from main import app as orch_app
client = TestClient(orch_app)


@pytest.fixture(scope="module")
def live_validator():
    """Starts the real answer-validator-api service as a live subprocess for true HTTP integration testing."""
    repo_root = orch_dir.parent
    val_dir = repo_root / "answer-validator-api"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", "8005"],
        cwd=str(val_dir)
    )
    time.sleep(1.5)  # Wait for startup
    yield proc
    proc.terminate()
    proc.wait()


class TestEndToEndPipeline:
    """
    End-to-End integration test across real HTTP boundaries:
    Request -> Orchestrator -> Mocked Agent -> Real Live Validator (:8005) -> Orchestrator -> UI Response
    """

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_case_a_valid_direct(self, mock_agent, live_validator):
        """Case A: Valid direct fact retrieved with evidence citation."""
        mock_agent.return_value = {
            "answer": "$142.5M",
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_017", "page": 1, "section": "Income Statement"}],
            "params": {"value": "$142.5M"},
            "validated": True,
            "_trace": {"latency_ms": 120}
        }

        resp = client.post("/ask", json={"question": "What was operating income?"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["validated"] is True
        assert data["answer_type"] == "direct"
        assert data["answer"] == "$142.5M"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["document_id"] == "doc_017"
        assert data["evidence"][0]["page"] == 1
        assert data["params"]["value"] == "$142.5M"

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_case_b_invalid_calculated_missing_formula(self, mock_agent, live_validator):
        """Case B: Agent returns calculated answer missing formula -> Live Validator rejects -> UI receives safe fallback."""
        mock_agent.return_value = {
            "answer": "13.4%",
            "answer_type": "calculated",
            "evidence": [{"document_id": "doc_041", "page": 2}],
            "params": {"value": 13.4}  # Missing required 'formula'!
        }

        resp = client.post("/ask", json={"question": "What was the growth rate?"})
        assert resp.status_code == 200
        data = resp.json()

        # The invalid answer MUST NOT be returned as a successful answer
        assert data["validated"] is False
        assert data["answer_type"] == "insufficient_evidence"
        assert data["answer"] == "Insufficient evidence to answer the question."
        assert "formula" in data["params"]["reason"]
        assert data["evidence"] == []

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_case_c_insufficient_evidence(self, mock_agent, live_validator):
        """Case C: Insufficient evidence response with empty evidence is accepted."""
        mock_agent.return_value = {
            "answer": "Insufficient evidence to answer the question.",
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "No document in the corpus reports restructuring costs."}
        }

        resp = client.post("/ask", json={"question": "What were restructuring costs?"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["validated"] is True
        assert data["answer_type"] == "insufficient_evidence"
        assert data["evidence"] == []
        assert "restructuring costs" in data["params"]["reason"]

    @patch("main.call_agent", new_callable=AsyncMock)
    def test_case_d_injected_root_field_rejected(self, mock_agent, live_validator):
        """Case D: Agent injects unauthorized root fields -> Rejected by Live Validator and stripped from response."""
        mock_agent.return_value = {
            "answer": "42",
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": "42"},
            "malicious_injected_key": "exploit_data"
        }

        resp = client.post("/ask", json={"question": "What is the secret?"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["validated"] is False
        assert data["answer_type"] == "insufficient_evidence"
        assert "malicious_injected_key" not in data
        assert "malicious_injected_key" in data["params"]["reason"]
