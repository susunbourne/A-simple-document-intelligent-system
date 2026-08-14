# Multi-Agent Document Intelligence System

An applied document intelligence pipeline for converting uploaded documents into structured, schema-validated records. The system combines **FastAPI**, **Docling**, **OpenAI structured outputs**, a lightweight **RAG** layer, and **PostgreSQL** to classify documents, retrieve relevant context, extract fields, and persist results.

This project started from a simpler bank-statement parser and was redesigned into a more extensible document intelligence system: parse first, route by document type, retrieve relevant sections, then extract through specialized agents.

---

## Why This Project

Many document extraction workflows fail because they either:

- hardcode logic for one document format,
- send entire long documents to an LLM without retrieval,
- rely on fragile JSON/string parsing,
- or return extracted values without validation or persistence.

This project explores a more product-ready pattern:

```text
document ingestion -> LLM routing -> RAG retrieval -> structured extraction -> validation -> database persistence
```

The current implementation supports bank statements and athlete contracts, but the architecture is designed so new document types can be added without rewriting the whole pipeline.

---

## Core Pipeline

```text
User Upload
    |
    v
FastAPI Endpoint
    |
    v
DoclingService
PDF/DOCX/image -> Markdown text
    |
    v
RouterAgent
LLM classifies document type and confidence
    |
    v
RAGService
chunking -> embeddings -> semantic retrieval
    |
    v
Specialized Extraction Agent
OpenAI structured outputs + Pydantic schema
    |
    v
Service Layer
transform and save records
    |
    v
PostgreSQL
```

---

## Key Features

- **Multi-format document ingestion**: Uses Docling to convert PDFs, DOCX files, spreadsheets, slides, and images into Markdown-like text.
- **LLM router agent**: Classifies the document type before extraction and rejects low-confidence routing decisions.
- **Lightweight RAG layer**: Chunks parsed text, creates OpenAI embeddings, retrieves relevant chunks with cosine similarity, and passes retrieved context to extraction agents.
- **Structured LLM extraction**: Uses OpenAI structured outputs with Pydantic models rather than ad hoc JSON parsing.
- **Validation-first design**: Pydantic schemas enforce field structure; router confidence gates avoid silently extracting from uncertain documents.
- **Database persistence**: Stores extracted bank statement and contract records using SQLAlchemy and PostgreSQL.
- **Extensible agent pattern**: New document types can be added through new schemas, agents, services, and workflow branches.

---

## How RAG Is Implemented

The RAG layer is intentionally lightweight and in-memory, designed for a single uploaded document at a time.

1. **Chunking**
   - The parsed Markdown text is split by paragraphs.
   - Chunks are kept around `1800` characters.
   - Long paragraphs are split directly.
   - Overlap is used to reduce boundary loss when important facts sit near chunk edges.

2. **Embedding**
   - Each chunk is embedded with `text-embedding-3-small`.
   - The query for retrieval is also embedded.

3. **Task-specific retrieval**
   - The retrieval query changes by document type.
   - For bank statements, the query focuses on transaction descriptions, dates, debits, credits, and amounts.
   - For contracts, the query focuses on parties, dates, terms, compensation, value, and currency.

4. **Extraction over retrieved context**
   - Extraction agents receive retrieved chunks instead of the whole document.
   - This reduces noisy context, lowers token cost, and makes the output easier to trace back to source text.

This is a prototype RAG layer rather than a full production vector database. The next architecture step would be persistent vector storage, page/section metadata, source citations, and retrieval evaluation metrics.

---

## Supported Document Types

| Document type | Router value | Extracted fields |
|---|---|---|
| Bank statement | `bank_statement` | `description`, `amount`, `transaction_date` |
| Athlete contract | `athlete contract` | `contract_name`, `party_a`, `party_b`, `effective_date`, `expiration_date`, `contract_value`, `currency` |

The configuration also reserves router labels for future document types such as transfer agreements and sponsorship/endorsement contracts.

---

## Project Structure

```text
src/
├── main.py
├── api/
│   └── statement.py
├── agents/
│   ├── router_agent.py
│   ├── contract_agent.py
│   └── document_agent.py
├── services/
│   ├── docling_service.py
│   ├── rag_service.py
│   ├── extraction_service.py
│   ├── statement_service.py
│   └── contract_service.py
├── workflows/
│   └── statement_workflow.py
├── schemas/
│   ├── router.py
│   ├── bank_statement.py
│   └── athlete_contract.py
├── models/
│   ├── statement.py
│   └── athlete_contract.py
└── db/
    ├── database.py
    └── session.py
```

---

## Tech Stack

| Layer | Tools |
|---|---|
| API | FastAPI, Uvicorn |
| Document parsing | Docling |
| LLM routing/extraction | OpenAI API, structured outputs |
| RAG | OpenAI embeddings, in-memory vector index, cosine similarity |
| Validation | Pydantic |
| Persistence | SQLAlchemy, PostgreSQL |
| Configuration | pydantic-settings, `.env` |

---

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/docdb
OPENAI_API_KEY=your_openai_api_key
```

Run the API:

```bash
uvicorn src.main:app --reload
```

Open the interactive docs:

```text
http://localhost:8000/docs
```

---

## API Example

### `POST /statements/upload`

Upload a document using `multipart/form-data` with a `file` field.

Example bank statement response:

```json
{
  "statements": [
    {
      "id": 1,
      "filename": "statement.pdf",
      "description": "AMAZON MARKETPLACE",
      "amount": 49.99,
      "transaction_date": "2024-01-15",
      "created_at": "2024-06-01T12:00:00Z"
    }
  ]
}
```

Example contract response:

```json
{
  "contracts": [
    {
      "contract_id": 1,
      "filename": "contract.pdf",
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

## Architecture Notes And Next Steps

Useful next improvements:

- Add a persistent vector database such as Chroma, pgvector, or FAISS for cross-document retrieval.
- Store chunk metadata such as page number, section title, document ID, and source offsets.
- Return source citations for each extracted field.
- Add a small evaluation dataset with manually validated ground truth.
- Compare full-document extraction vs. RAG-based extraction using field-level accuracy, missing-field rate, hallucination rate, and source-support checks.
- Add a human review dashboard for low-confidence routing or extraction outputs.
- Move long-running Docling/LLM jobs to a queue such as Celery, RQ, or FastAPI background tasks.
- Add unit tests for chunking, retrieval ranking, schema validation, and workflow routing.

---

## Public Repository Note

Do not commit `.env` files, API keys, private documents, or real user/customer data. This repository is intended to show the architecture and implementation pattern, not private source documents.
