# LEDGER Windows PowerShell Unified Startup Script
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "     LEDGER Microservices Startup (PowerShell)      " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

$Root = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source

Write-Host "Using Python: $Python" -ForegroundColor Gray
Write-Host "Working Root: $Root" -ForegroundColor Gray

# 1. Answer Validator API (Port 8005)
Write-Host "`n[1/5] Starting answer-validator-api on port 8005..." -ForegroundColor Green
$p_val = Start-Process -FilePath $Python -ArgumentList "-m uvicorn main:app --port 8005" -WorkingDirectory "$Root\answer-validator-api" -PassThru

# 2. Document Processor API (Port 8001)
Write-Host "[2/5] Starting document_processor on port 8001..." -ForegroundColor Green
$p_doc = Start-Process -FilePath $Python -ArgumentList "-m uvicorn doc_processor_api:app --port 8001" -WorkingDirectory "$Root\document_processor" -PassThru

# 3. Retrieval API (Port 8002)
Write-Host "[3/5] Starting retrieval-api on port 8002..." -ForegroundColor Green
$p_ret = Start-Process -FilePath $Python -ArgumentList "-m uvicorn main:app --port 8002" -WorkingDirectory "$Root\retrieval-api" -PassThru

# 4. Agent Service (Port 8003) - Note: inject VALIDATOR_URL and RETRIEVAL_URL
Write-Host "[4/5] Starting agent-service on port 8003..." -ForegroundColor Green
$env:VALIDATOR_URL = "http://localhost:8005"
$env:RETRIEVAL_URL = "http://localhost:8002"
$p_agent = Start-Process -FilePath $Python -ArgumentList "-m uvicorn main:app --port 8003" -WorkingDirectory "$Root\agent-service" -PassThru

# 5. Orchestrator API (Port 8000)
Write-Host "[5/5] Starting orchestrator-api on port 8000..." -ForegroundColor Green
$env:AGENT_SERVICE_URL = "http://localhost:8003"
$env:VALIDATOR_SERVICE_URL = "http://localhost:8005"
$env:DOC_PROCESSOR_URL = "http://localhost:8001"
$env:RETRIEVAL_SERVICE_URL = "http://localhost:8002"
$p_orch = Start-Process -FilePath $Python -ArgumentList "-m uvicorn main:app --port 8000" -WorkingDirectory "$Root\orchestrator-api" -PassThru

Write-Host "`nAll services launched. Press Ctrl+C in their respective windows or close this terminal to stop." -ForegroundColor Yellow
