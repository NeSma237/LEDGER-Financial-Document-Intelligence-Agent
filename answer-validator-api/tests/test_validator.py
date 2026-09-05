import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ===================== VALID CASES =====================

class TestValidDirect:
    def test_valid_direct(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_017", "page": 1, "section": "Income Statement"}],
            "params": {"value": "$142.5M"}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_valid_direct_numeric_value(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 0}],
            "params": {"value": 142.5}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


class TestValidCalculated:
    def test_valid_calculated(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "calculated",
            "evidence": [
                {"document_id": "doc_041", "page": 2, "section": "Operating Expenses"},
                {"document_id": "doc_041", "page": 2, "section": "Operating Expenses"}
            ],
            "params": {"value": 13.4, "formula": "(3875-3410)/3410*100"}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


class TestValidMultiSpan:
    def test_valid_multi_span(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_022", "page": 3, "section": "Operating Expenses"}],
            "params": {"values": ["Marketing", "R&D", "Logistics"]}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


class TestValidInsufficientEvidence:
    def test_valid_insufficient_evidence(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "No document in the indexed corpus reports restructuring expenses."}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


# ===================== INVALID CASES =====================

class TestInvalidMissingAnswerType:
    def test_missing_answer_type(self):
        resp = client.post("/validate_answer", json={
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "answer_type" in resp.json()["reason"]


class TestInvalidUnknownAnswerType:
    def test_unknown_answer_type(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "comparison",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "Unknown answer_type" in resp.json()["reason"]


class TestInvalidMissingEvidence:
    def test_missing_evidence_field(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_empty_evidence_when_required(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "evidence" in resp.json()["reason"].lower()


class TestInvalidMissingParams:
    def test_missing_params(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}]
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInvalidMissingValue:
    def test_direct_missing_value(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "value" in resp.json()["reason"]


class TestInvalidWrongValueType:
    def test_direct_wrong_value_type(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": ["not", "a", "scalar"]}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInvalidMissingFormula:
    def test_calculated_missing_formula(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "calculated",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": 13.4}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "formula" in resp.json()["reason"]


class TestInvalidWrongFormulaType:
    def test_calculated_wrong_formula_type(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "calculated",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": 13.4, "formula": 12345}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInvalidMissingValues:
    def test_multi_span_missing_values(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "values" in resp.json()["reason"]


class TestInvalidWrongValuesType:
    def test_multi_span_wrong_values_type(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": "not a list"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInvalidMalformedEvidence:
    def test_evidence_missing_document_id(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"page": 1}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_evidence_empty_document_id(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "", "page": 1}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInvalidPageType:
    def test_evidence_invalid_page_type(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": "not_a_number"}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_evidence_negative_page(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": -1}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_evidence_boolean_page_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": True}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInvalidExtraFields:
    def test_extra_root_field_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": "test"},
            "injected_root_field": "hack"
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "injected_root_field" in resp.json()["reason"]

    def test_extra_params_field_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": "test", "extra_param": 123}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False
        assert "extra_param" in resp.json()["reason"]

    def test_extra_evidence_field_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1, "extra_info": "bad"}],
            "params": {"value": "test"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestMultiSpanElementValidation:
    def test_empty_string_element_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": [""]}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_whitespace_string_element_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": ["   "]}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_mixed_valid_and_empty_element_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": ["A", ""]}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_mixed_valid_and_whitespace_element_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": ["A", "   "]}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_valid_strings_accepted(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": ["A", "B"]}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_valid_numbers_accepted(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "multi_span",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"values": [1, 2, 3]}
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


class TestStrictTypeChecks:
    def test_calculated_boolean_value_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "calculated",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": True, "formula": "1+1"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_calculated_string_value_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "calculated",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": "13.4", "formula": "1+1"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_calculated_missing_value_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "calculated",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"formula": "1+1"}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_direct_boolean_value_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "direct",
            "evidence": [{"document_id": "doc_001", "page": 1}],
            "params": {"value": True}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestInsufficientEvidenceStrict:
    def test_missing_reason_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False

    def test_empty_reason_rejected(self):
        resp = client.post("/validate_answer", json={
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": ""}
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestHealthCheck:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

