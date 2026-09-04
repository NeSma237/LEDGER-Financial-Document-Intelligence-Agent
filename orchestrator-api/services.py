import httpx
import logging
from typing import Any, Dict, Optional
from config import settings

logger = logging.getLogger("orchestrator")


class ServiceError(Exception):
    """Raised when a downstream service call fails."""
    def __init__(self, service: str, message: str, status_code: Optional[int] = None):
        self.service = service
        self.message = message
        self.status_code = status_code
        super().__init__(f"[{service}] {message}")


async def call_agent(question: str, conversation_id: str) -> Dict[str, Any]:
    """Forward a question to the agent service."""
    url = f"{settings.AGENT_SERVICE_URL}/agent/answer"
    logger.info(f"[ORCHESTRATOR] Sending question to agent: {url}")
    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json={
                "question": question,
                "conversation_id": conversation_id
            })
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[ORCHESTRATOR] Agent responded with answer_type='{data.get('answer_type')}'")
            return data
    except httpx.TimeoutException:
        logger.error(f"[ORCHESTRATOR] Agent service timed out at {url}")
        raise ServiceError("agent-service", "Request timed out", status_code=504)
    except httpx.ConnectError:
        logger.error(f"[ORCHESTRATOR] Cannot connect to agent service at {url}")
        raise ServiceError("agent-service", "Service unavailable", status_code=503)
    except httpx.HTTPStatusError as e:
        logger.error(f"[ORCHESTRATOR] Agent service returned HTTP {e.response.status_code}")
        raise ServiceError("agent-service", f"HTTP {e.response.status_code}", status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Unexpected error calling agent: {e}")
        raise ServiceError("agent-service", str(e))


async def call_validator(answer_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send an answer to the validator service for validation."""
    url = f"{settings.VALIDATOR_SERVICE_URL}/validate_answer"
    logger.info(f"[ORCHESTRATOR] Sending answer to validator: {url}")
    # Forward the payload without pipeline wrapper metadata (_trace, validated, answer)
    # Any unexpected extra fields injected by the agent are preserved so the validator can reject them
    validation_payload = {
        k: v for k, v in answer_payload.items()
        if k not in ("_trace", "validated", "answer")
    }
    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=validation_payload)
            data = resp.json()
            logger.info(f"[ORCHESTRATOR] Validator responded: valid={data.get('valid')}")
            return data
    except httpx.TimeoutException:
        logger.error(f"[ORCHESTRATOR] Validator service timed out at {url}")
        raise ServiceError("answer-validator-api", "Request timed out", status_code=504)
    except httpx.ConnectError:
        logger.error(f"[ORCHESTRATOR] Cannot connect to validator at {url}")
        raise ServiceError("answer-validator-api", "Service unavailable", status_code=503)
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Unexpected error calling validator: {e}")
        raise ServiceError("answer-validator-api", str(e))


async def call_doc_processor(file_content: bytes, filename: str) -> Dict[str, Any]:
    """Send a PDF to the document processor."""
    url = f"{settings.DOC_PROCESSOR_URL}/process"
    logger.info(f"[ORCHESTRATOR] Sending document '{filename}' to processor: {url}")
    try:
        async with httpx.AsyncClient(timeout=120) as client:  # Longer timeout for PDF processing
            files = {"file": (filename, file_content, "application/pdf")}
            resp = await client.post(url, files=files)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[ORCHESTRATOR] Document processed: {data.get('document_id')}")
            return data
    except httpx.TimeoutException:
        logger.error(f"[ORCHESTRATOR] Doc processor timed out at {url}")
        raise ServiceError("doc-processor-api", "Request timed out", status_code=504)
    except httpx.ConnectError:
        logger.error(f"[ORCHESTRATOR] Cannot connect to doc processor at {url}")
        raise ServiceError("doc-processor-api", "Service unavailable", status_code=503)
    except httpx.HTTPStatusError as e:
        logger.error(f"[ORCHESTRATOR] Doc processor returned HTTP {e.response.status_code}")
        raise ServiceError("doc-processor-api", f"HTTP {e.response.status_code}", status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Unexpected error calling doc processor: {e}")
        raise ServiceError("doc-processor-api", str(e))


async def call_retrieval_index(document_id: str, pages: list) -> Dict[str, Any]:
    """Index a processed document in the retrieval service."""
    url = f"{settings.RETRIEVAL_SERVICE_URL}/index"
    logger.info(f"[ORCHESTRATOR] Indexing document '{document_id}' in retrieval: {url}")
    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json={
                "document_id": document_id,
                "pages": pages
            })
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[ORCHESTRATOR] Document indexed: {data.get('chunks_indexed')} chunks")
            return data
    except httpx.TimeoutException:
        logger.error(f"[ORCHESTRATOR] Retrieval service timed out at {url}")
        raise ServiceError("retrieval-api", "Request timed out", status_code=504)
    except httpx.ConnectError:
        logger.error(f"[ORCHESTRATOR] Cannot connect to retrieval at {url}")
        raise ServiceError("retrieval-api", "Service unavailable", status_code=503)
    except httpx.HTTPStatusError as e:
        logger.error(f"[ORCHESTRATOR] Retrieval service returned HTTP {e.response.status_code}")
        raise ServiceError("retrieval-api", f"HTTP {e.response.status_code}", status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Unexpected error calling retrieval: {e}")
        raise ServiceError("retrieval-api", str(e))
