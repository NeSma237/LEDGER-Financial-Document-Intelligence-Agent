# LEDGER — Financial Document Intelligence Agent

An Agentic RAG system that reads financial reports (PDF) and answers questions about them with a citation for every answer — no hallucination.

## Architecture

The project is built as 7 separate microservices communicating over HTTP:

| # | Service | Framework | Owner |
|---|---|---|---|
| 1 | `orchestrator-api` | FastAPI | Hassan Mohamed |
| 2 | `doc-processor-api` | FastAPI + OCR/Layout model | MounReda |
| 3 | `retrieval-api` | FastAPI + Vector DB | Nesma Nasser |
| 4 | `agent-service` | LangGraph | Thomas Mina |
| 5 | `eval-service` | FastAPI + Langfuse | Mohamed Aboulfottouh |
| 6 | `ui-service` | Gradio | Marwan Bahy |
| 7 | `answer-validator-api` | FastAPI/Flask | TBD |

## Running the Project

```bash
# TODO: run instructions (Docker Compose or startup script)
```

## Repo Structure

```
ledger-repo/
├── orchestrator-api/       # Central nervous system - routes requests between services
├── doc-processor-api/      # Converts raw PDFs into structured representation (text/tables/pages)
├── retrieval-api/          # Semantic search + BM25 + reranking
├── agent-service/          # The "Brain" - LangGraph agent
├── eval-service/           # Evaluation and tracing (Langfuse)
├── ui-service/             # Gradio UI (chat + dashboard)
├── answer-validator-api/   # Answer schema validation
├── docs/                   # Project docs (schema, API contracts, failure analysis)
├── docker-compose.yml      # (optional - bonus)
└── README.md
```

## Data
- [TAT-DQA Dataset](https://huggingface.co/datasets/next-tat/TAT-DQA) — for Document Intelligence
- `questions_setA_practice` (100 questions) — for testing the RAG pipeline

⚠️ **Important rule**: The ingestion pipeline must take raw PDFs as input. The dataset's own pre-parsed JSON must NOT be used as the document representation in production.

## Branching Strategy
- `main` — protected, no direct push
- Feature branches: `feature/<service-name>-<short-desc>` (e.g. `feature/retrieval-chunking`)
- Fix branches: `bugfix/<short-desc>`
- All merges go through Pull Requests only

## Definition of Done
See [`docs/definition-of-done.md`](docs/definition-of-done.md)

## Team & Mentors
- [@Mohamedh0](https://github.com/Mohamedh0)
- [@BASSAT-BASSAT](https://github.com/BASSAT-BASSAT)
- [@Gamal-Abouelhamd](https://github.com/Gamal-Abouelhamd)
- [@JanaGh7](https://github.com/JanaGh7)
- [@Asemgamal955](https://github.com/Asemgamal955)
- [@esraakh299](https://github.com/esraakh299)
- [@HanaRamah](https://github.com/HanaRamah)
