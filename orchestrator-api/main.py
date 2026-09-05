import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from schemas import AskRequest, AskResponse, IngestResponse, DocumentsResponse, ErrorResponse
from services import call_agent, call_validator, call_doc_processor, call_retrieval_index, ServiceError
from adapters import adapt_docling_output
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("orchestrator")

app = FastAPI(
    title="LEDGER Orchestrator API",
    description="Central nervous system for the LEDGER Financial Document Intelligence system",
    version="1.0.0"
)

# In-memory document registry (tracks ingested documents)
_document_registry: list = []


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Main question-answering pipeline:
    1. Forward question to agent-service
    2. Validate agent's answer via answer-validator-api
    3. Return validated answer to UI (or reject invalid answers)
    """
    logger.info(f"[ORCHESTRATOR] Received question: '{request.question}' (conversation_id={request.conversation_id})")

    # Step 1: Call the Agent
    try:
        agent_response = await call_agent(request.question, request.conversation_id)
    except ServiceError as e:
        logger.error(f"[ORCHESTRATOR] Agent service failed: {e.message}")
        return JSONResponse(
            status_code=e.status_code or 502,
            content={"error": f"Agent service error: {e.message}",
                     "detail": "The agent service is unavailable or returned an error."}
        )

    # Step 2: Validate the response structure
    if not isinstance(agent_response, dict):
        logger.error("[ORCHESTRATOR] Agent returned non-dict response")
        return JSONResponse(
            status_code=502,
            content={"error": "Invalid response from agent service",
                     "detail": "Agent response is not a valid JSON object."}
        )

    answer_type = agent_response.get("answer_type")
    if not answer_type:
        logger.error("[ORCHESTRATOR] Agent response missing answer_type")
        return JSONResponse(
            status_code=502,
            content={"error": "Malformed agent response",
                     "detail": "Agent response is missing 'answer_type'."}
        )

    # Step 3: Send to Answer Validator
    try:
        validator_result = await call_validator(agent_response)
    except ServiceError as e:
        logger.error(f"[ORCHESTRATOR] Validator service failed: {e.message}")
        return JSONResponse(
            status_code=e.status_code or 502,
            content={"error": f"Validator service error: {e.message}",
                     "detail": "The answer validator is unavailable."}
        )

    is_valid = validator_result.get("valid", False)

    # Step 4: Handle validation result
    if not is_valid:
        val_reason = validator_result.get("reason", "Unknown validation failure")
        logger.warning(f"[ORCHESTRATOR] Answer rejected by validator: {val_reason}")

        # Return a safe insufficient_evidence response instead of the invalid answer
        return AskResponse(
            answer="Insufficient evidence to answer the question.",
            answer_type="insufficient_evidence",
            evidence=[],
            params={"reason": f"Validation failed: {val_reason}"},
            validated=False,
            _trace=agent_response.get("_trace")
        )

    # Step 5: Return validated answer to UI using typed AskResponse model
    logger.info(f"[ORCHESTRATOR] Returning validated answer of type '{answer_type}'")
    return AskResponse(
        answer=agent_response.get("answer", ""),
        answer_type=answer_type,
        evidence=agent_response.get("evidence", []),
        params=agent_response.get("params", {}),
        validated=True,
        _trace=agent_response.get("_trace")
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)):
    """
    Document ingestion pipeline:
    1. Forward PDF to doc-processor-api
    2. Adapt processed content to retrieval-api IndexRequest format
    3. Send adapted pages to retrieval-api for indexing
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    logger.info(f"[ORCHESTRATOR] Ingesting document: {file.filename}")

    # Step 1: Read file content
    file_content = await file.read()

    # Step 2: Process the document
    try:
        processor_result = await call_doc_processor(file_content, file.filename)
    except ServiceError as e:
        logger.error(f"[ORCHESTRATOR] Document processing failed: {e.message}")
        return JSONResponse(
            status_code=e.status_code or 502,
            content={"error": f"Document processor error: {e.message}",
                     "detail": "Failed to process the uploaded document."}
        )

    document_id = processor_result.get("document_id", file.filename)
    raw_docling_dict = processor_result.get("raw_docling_dict", {})

    # Step 3: Adapt docling output to Retrieval IndexRequest format
    adapted = adapt_docling_output(document_id, raw_docling_dict)
    pages = adapted.get("pages", [])

    if not pages:
        logger.error(f"[ORCHESTRATOR] No pages could be extracted from document '{document_id}'")
        return JSONResponse(
            status_code=422,
            content={"error": "Document conversion failed",
                     "detail": f"No extractable text or table pages found in '{document_id}'.",
                     "document_id": document_id}
        )

    # Step 4: Index in retrieval service
    try:
        index_result = await call_retrieval_index(document_id, pages)
    except ServiceError as e:
        logger.error(f"[ORCHESTRATOR] Indexing failed: {e.message}")
        return JSONResponse(
            status_code=e.status_code or 502,
            content={"error": f"Retrieval indexing error: {e.message}",
                     "detail": "Document was processed but indexing failed.",
                     "document_id": document_id}
        )

    chunks_indexed = index_result.get("chunks_indexed", 0)
    if chunks_indexed == 0:
        logger.warning(f"[ORCHESTRATOR] Indexing returned 0 chunks for document '{document_id}'")
        return JSONResponse(
            status_code=422,
            content={"error": "Indexing resulted in zero chunks",
                     "detail": "The retrieval service could not index any chunks from this document.",
                     "document_id": document_id}
        )

    # Step 5: Track document in registry
    _document_registry.append({
        "document_id": document_id,
        "chunks_indexed": chunks_indexed
    })

    logger.info(f"[ORCHESTRATOR] Document '{document_id}' ingested: {chunks_indexed} chunks indexed")
    return IngestResponse(
        document_id=document_id,
        chunks_indexed=chunks_indexed,
        status="success",
        message=f"Document '{document_id}' processed and indexed successfully"
    )


@app.get("/documents", response_model=DocumentsResponse)
async def list_documents():
    """List all ingested documents."""
    return DocumentsResponse(
        documents=_document_registry,
        total=len(_document_registry)
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
