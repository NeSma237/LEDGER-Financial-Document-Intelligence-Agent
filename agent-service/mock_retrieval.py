from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Mock Retrieval API")

# mooooooooock retrieval
MOCK_CHUNKS = [
    {
        "document_id": "cts_2019_annual_report",
        "page": 2,
        "section": "Inventories",
        "content": "Finished goods inventory for CTS Corporation as of December 31, 2019 was $9,447 thousand.",
        "score": 0.94,
        "content_type": "table"
    },
    {
        "document_id": "jabil_2019_annual_report",
        "page": 1,
        "section": "Inventories",
        "content": "Jabil Inc. reported finished goods of $314,258 thousand for the fiscal year ending 2019.",
        "score": 0.91,
        "content_type": "table"
    },
    {
        "document_id": "doc_017",
        "page": 1,
        "section": "Income Statement",
        "content": "Operating income was $142.5M in 2020, compared to $128.3M in 2019.",
        "score": 0.88,
        "content_type": "text"
    }
]

@app.post("/search_documents")
def search_documents(body: dict):
    return {"results": MOCK_CHUNKS}

@app.post("/search_tables")
def search_tables(body: dict):
    table_chunks = [c for c in MOCK_CHUNKS if c["content_type"] == "table"]
    return {"results": table_chunks}

@app.post("/filter_documents")
def filter_documents(body: dict):
    doc_id = body.get("document_id", "")
    filtered = [c for c in MOCK_CHUNKS if c["document_id"] == doc_id]
    return {"results": filtered if filtered else MOCK_CHUNKS[:1]}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)