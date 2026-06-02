# A Simple Document Intelligence System

I built a bank parser platform beforehand, but it feels kinda outdated, so I learned from the Internet and combined what I've learned from class to build a document intelligent system, trying to build a more "Product-Ready" project.

---

## Overview

This is a document intelligence pipeline built with **FastAPI**, **Docling**, **OpenAI structured outputs**, and **PostgreSQL**. The system accepts uploaded documents (PDF, DOCX, images, etc.), converts them to structured text, classifies the document type via an LLM-powered router, and dispatches to the appropriate extraction agent — all returning clean, schema-validated JSON persisted to a relational database.

The core design idea: instead of hardcoding logic per document type, route first, then extract. This makes it easy to add new document types without touching existing extraction logic.

---

## Architecture

```
User Upload (POST /statements/upload)
         │
         ▼
   DoclingService              ← converts raw bytes → Markdown text
         │
         ▼
    RouterAgent                ← GPT-4o-mini classifies document type
    (confidence gate)          ← rejects if confidence < 0.5
         │
    ┌────┴────────────────┐
    ▼                     ▼
BankStatement Agent   Contract Agent      (more agents extensible here)
    │                     │
    ▼                     ▼
ExtractionService   ContractExtractionService
(structured output   (structured output w/
 w/ JSON schema)      JSON schema)
    │                     │
    ▼                     ▼
StatementService    ContractService
(SQLAlchemy ORM)    (SQLAlchemy ORM)
    │                     │
    └────────┬────────────┘
             ▼
        PostgreSQL DB
   (bank_statements / athlete_contracts)
```

The full architecture diagram (including RAG, vector DB, task queue, and metrics layers) lives in [`docs/architecture.mmd`](docs/architecture.mmd).

---

## Key Design Decisions

**1. Router-first pattern**
A dedicated `RouterAgent` classifies the document before any extraction happens. It returns a `form_type` and a `confidence` score. If confidence falls below `0.5`, the pipeline refuses to process rather than silently hallucinating data. This is a deliberate design choice — fail loudly rather than return bad structured data.

**2. OpenAI Structured Outputs (not prompt hacking)**
Both extraction agents use `client.responses.parse()` with Pydantic models as `text_format`. This enforces JSON Schema at the API level, not via string parsing. No regex, no `json.loads()` error handling — the schema is guaranteed by the model.

**3. Docling for document ingestion**
[Docling](https://github.com/DS4SD/docling) handles multi-format document conversion (PDF, DOCX, images) to Markdown. It supports GPU acceleration via `AcceleratorDevice.AUTO` — if a CUDA-capable GPU is present, it uses it automatically (speeds up layout and table detection significantly).

**4. Workflow orchestration**
`StatementWorkflow` is a single class that wires together Docling → Router → Agent → Service. The API layer just calls `workflow.run_analysis_flow()` and gets back a list of ORM records. No business logic leaks into the API router.

**5. Extensibility**
New document types are added by:
- Adding a new schema to `src/schemas/`
- Adding a new agent to `src/agents/`
- Adding a new service to `src/services/`
- Adding a branch in `StatementWorkflow.run_analysis_flow()`
- Registering the type string in `Valid_FORM_TYPES` in `config.py`

---

## Project Structure

```
src/
├── main.py                   # FastAPI app entry point, lifespan DB init
├── core/
│   └── config.py             # Pydantic Settings (env-based config)
├── api/
│   └── statement.py          # POST /statements/upload endpoint
├── workflows/
│   └── statement_workflow.py # Orchestration: Docling → Router → Agent → DB
├── agents/
│   ├── router_agent.py       # LLM document type classifier
│   ├── contract_agent.py     # Athlete contract extraction agent
│   └── document_agent.py     # (placeholder for future generic agent)
├── services/
│   ├── docling_service.py    # Docling document-to-Markdown converter
│   ├── extraction_service.py # Bank statement extraction (structured output)
│   ├── statement_service.py  # ORM layer for BankStatement
│   └── contract_service.py   # ORM layer for AthleteContract
├── models/
│   ├── statement.py          # SQLAlchemy model: bank_statements table
│   ├── athlete_contract.py   # SQLAlchemy model: athlete_contracts table
│   └── user.py               # (placeholder)
├── schemas/
│   ├── bank_statement.py     # Pydantic schemas: extraction + response
│   ├── athlete_contract.py   # Pydantic schemas: extraction + response
│   ├── router.py             # RouterDeterminationResult schema
│   └── user.py               # (placeholder)
└── db/
    ├── database.py           # SQLAlchemy engine + Base
    └── session.py            # get_db dependency
docs/
├── architecture.mmd          # Full Mermaid architecture diagram
└── ARCHITECTURE.md           # Diagram export instructions
```

---

## Supported Document Types

| Type | `form_type` value | Extracted Fields |
|---|---|---|
| Bank Statement | `bank_statement` | `description`, `amount`, `transaction_date` |
| Athlete Contract | `athlete contract` | `contract_name`, `party_a`, `party_b`, `effective_date`, `expiration_date`, `contract_value`, `currency` |

Configured in `config.py` under `Valid_FORM_TYPES`. The router also handles `transfer agreement` and `Sponsorship & endorsement contract` — agents for those are the next step.

---

## Supported Input Formats

`.pdf` · `.docx` · `.xlsx` · `.pptx` · `.png` · `.jpg`

---

## Installation

```bash
pip install -r requirements.txt
```

If you have an NVIDIA GPU (recommended for Docling's layout/table detection):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

---

## Configuration

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/docdb
OPENAI_API_KEY=sk-...
```

---

## Running the Server

```bash
uvicorn src.main:app --reload
```

The app auto-creates database tables on startup via `Base.metadata.create_all()`.

API docs available at `http://localhost:8000/docs`.

---

## API

### `POST /statements/upload`

Upload a document for classification and extraction.

**Request:** `multipart/form-data` with a `file` field.

**Response (bank statement):**
```json
{
  "statements": [
    {
      "id": 1,
      "filename": "chase_jan2024.pdf",
      "description": "AMAZON MARKETPLACE",
      "amount": 49.99,
      "transaction_date": "2024-01-15",
      "created_at": "2024-06-01T12:00:00Z"
    }
  ]
}
```

**Response (athlete contract):**
```json
{
  "contracts": [
    {
      "contract_id": 1,
      "filename": "nike_deal.pdf",
      "contract_name": "Sponsorship Agreement",
      "party_a": "Nike Inc.",
      "party_b": "John Smith",
      "effective_date": "2024-01-01",
      "expiration_date": "2026-12-31",
      "contract_value": 5000000.0,
      "currency": "USD",
      "created_at": "2024-06-01T12:00:00Z"
    }
  ]
}
```

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI |
| Document Parsing | Docling |
| LLM / Extraction | OpenAI GPT-4o-mini (structured outputs) |
| Data Validation | Pydantic v2 |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Config Management | pydantic-settings |
| GPU Acceleration | PyTorch / CUDA (optional) |

---

## What's Next

- [ ] Generic document agent for unsupported types
- [ ] Extraction agents for `transfer agreement` and sponsorship contracts
- [ ] Streamlit dashboard for browsing extracted records
- [ ] Chunking + vector retrieval (RAG layer) for long documents
- [ ] Confidence-based human review queue
- [ ] Task queue (Celery/RQ) for async processing of large files