# Forward-Deployed AI Data Harness for Unstructured Documents

An FDE-oriented AI data harness for turning messy customer documents into reliable, schema-validated business records. It combines **document parsing**, **chunking with source offsets**, **task-specific RAG**, **context assembly**, **structured extraction**, **automation**, and **evidence-linked persistence** to show how raw text becomes controlled model input and auditable data.

The project models the data-layer work of a Forward-Deployed Engineer: understand an unfamiliar customer document, define the data contract, build the processing path, handle uncertainty, and measure whether the output is trustworthy. It started from a bank-statement parser and was redesigned into a reusable document intelligence workflow.

> **FDE positioning:** This is not just an LLM demo. It is an AI automation harness for the path from customer-owned unstructured data to validated output, human review, provenance, and measurable quality.

---

## Explore The System

- **[Public workflow walkthrough](https://document-intelligence-playground-jsu.sujy040913.chatgpt.site/):** a curated, no-customer-data walkthrough of the operator experience.
- **[System and workflow showcase](docs/PORTFOLIO_SHOWCASE.md):** layer-by-layer architecture, both core workflows, technical skills, Azure boundaries, and evidence-based readiness limits.
- **[Architecture and data flow](docs/ARCHITECTURE.md):** the full request, data, and control-plane diagram.
- **[Production review](docs/PRODUCTION_REVIEW.md):** implemented controls, evidence gaps, assumptions, and next production gates.
- **[Portfolio case study](docs/PORTFOLIO_CASE_STUDY.md):** customer problem to technical decisions and verification evidence.

The public walkthrough is intentionally a safe fixture. This repository contains
the implementation and testable control-plane behavior; it does not include
customer documents, access tokens, or API keys.

![FDE document intelligence architecture](docs/architecture.svg)

---

## Why This Is FDE Work

In a real customer engagement, the hard question is not “which model should we call?” It is “how do we make this customer's messy data usable, testable, and safe enough to support a business workflow?” This project makes that reasoning concrete.

## Why This Project

Many document extraction workflows fail because they either:

- hardcode logic for one document format,
- send entire long documents to an LLM without retrieval,
- rely on fragile JSON/string parsing,
- or return extracted values without validation or persistence.

This project implements a harness-engineering pattern:

```text
durable intake -> leased worker -> parsing -> chunking -> retrieval -> context assembly -> structured extraction -> validation -> review/persistence
```

The current implementation supports bank statements and athlete contracts, but the architecture is designed so new document types can be added without rewriting the whole pipeline.

---

## Core Pipeline

```text
Client Upload + Idempotency Key
    |
    v
FastAPI returns 202 + job_id
    |
    v
Private content-addressed source store
Local volume in dev / Azure Blob with Managed Identity in cloud
    |
    v
PostgreSQL ingestion job
lease + retry + recovery + stage
    |
    v
Independent ingestion worker
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
- **Durable asynchronous intake**: Uploads are streamed to content-addressed storage and accepted with `202 Accepted`; parsing and model calls run in an independent worker.
- **Incremental directory backfill**: A bounded connector command walks supported files and derives stable source-version idempotency keys, so repeated backfills skip unchanged work while changed bytes create a new job.
- **Recoverable job state machine**: PostgreSQL jobs use idempotency keys, bounded retries, exponential backoff, worker leases, lease recovery, and progress stages.
- **Cloud storage boundary**: Local development uses a shared volume; Azure deployments can use private Blob Storage with `DefaultAzureCredential` rather than storage keys.
- **Identity-bound tenant authorization**: In Entra mode, the API validates signed `tid`/`oid` claims and then resolves an active workspace membership and role before every ingestion, read, retry, or operations request.
- **LLM router agent**: Classifies the document type before extraction and rejects low-confidence routing decisions.
- **Lightweight RAG layer**: Chunks parsed text, creates OpenAI embeddings, retrieves relevant chunks with cosine similarity, and passes retrieved context to extraction agents.
- **Context assembly**: Builds model context under an explicit token budget and records included/dropped chunks.
- **Structured LLM extraction**: Uses OpenAI structured outputs with Pydantic models rather than ad hoc JSON parsing.
- **Validation-first design**: Pydantic schemas enforce field structure; router confidence gates avoid silently extracting from uncertain documents.
- **Database persistence**: Stores extracted bank statement and contract records using SQLAlchemy and PostgreSQL.
- **Production-oriented failure handling**: Returns stable error codes and request IDs, avoids raw document text in logs, and writes each upload in one database transaction.
- **Review-state persistence**: Marks incomplete extractions as `needs_review` instead of silently treating missing fields as completed records.
- **Auditable human review**: Reviewers can correct allowlisted fields, approve or reject records, and produce versioned actor plus before/after audit evidence; stale decisions are rejected.
- **Source chunk provenance**: Persists source documents, chunk offsets, token estimates, and selected RAG chunk IDs with extracted records when retrieval succeeds.
- **Model lineage**: Persists pipeline, router, embedding, and extraction model versions on each processed document.
- **Evaluation harness**: Scores recorded predictions for router accuracy, field accuracy, review-status accuracy, and evidence coverage.
- **Public retrieval benchmark**: Reproduces a no-cost BM25 baseline against 510 CUAD commercial contracts and 2,292 positive evidence queries aligned to the current contract schema.
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

This is a single-document retrieval layer, not a cross-document knowledge base. A persistent vector service is intentionally deferred until a customer requires historical/cross-document search or measured re-indexing cost justifies it.

---

## Supported Document Types

| Document type | Router value | Extracted fields |
|---|---|---|
| Bank statement | `bank_statement` | `description`, `amount`, `transaction_date` |
| Athlete contract | `athlete_contract` | `contract_name`, `party_a`, `party_b`, `effective_date`, `expiration_date`, `contract_value`, `currency` |

The configuration also reserves router labels for future document types such as transfer agreements and sponsorship/endorsement contracts.

---

## Project Structure

```text
src/
├── main.py
├── api/
│   └── statement.py
│   └── ingestion.py
├── agents/
│   ├── router_agent.py
│   ├── contract_agent.py
│   └── document_agent.py
├── services/
│   ├── docling_service.py
│   ├── rag_service.py
│   ├── extraction_service.py
│   ├── statement_service.py
│   ├── contract_service.py
│   └── document_service.py
│   ├── ingestion_service.py
│   └── object_store.py
├── repositories/
│   └── ingestion_repository.py
├── workers/
│   └── ingestion_worker.py
├── workflows/
│   └── statement_workflow.py
├── schemas/
│   ├── router.py
│   ├── bank_statement.py
│   └── athlete_contract.py
├── models/
│   ├── statement.py
│   ├── athlete_contract.py
│   └── document.py
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
| Durable source storage | Local content-addressed store or private Azure Blob |
| Work distribution | PostgreSQL lease/retry queue with independent worker |
| Cloud identity | Azure `DefaultAzureCredential` / Managed Identity for Blob |
| User identity | Microsoft Entra JWT validation + workspace membership RBAC |
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
# Keep true for quick local demos. Set false in staging/production and run Alembic migrations.
AUTO_CREATE_TABLES=true
DOCUMENT_SOURCE_BACKEND=local
DOCUMENT_SOURCE_ROOT=.dist/document-sources
AUTH_MODE=development
```

For Azure Blob source storage, set `DOCUMENT_SOURCE_BACKEND=azure_blob`,
`AZURE_BLOB_ACCOUNT_URL`, and `AZURE_BLOB_CONTAINER`. The application expects
workload identity/RBAC; it does not accept a storage account key setting.

Bootstrap a local workspace owner after migrations:

```bash
python -m scripts.bootstrap_workspace --workspace athletics-finance --display-name "Athletics Finance" --identity-tenant local --identity-subject local-developer
```

Development requests include `X-User-ID: local-developer`. For Entra, set
`AUTH_MODE=entra`, `ENTRA_TENANT_ID`, and `ENTRA_API_CLIENT_ID`; requests then
use a Bearer access token. `X-Tenant-ID` selects a workspace but never grants
access by itself: the server requires an active membership for the token's
tenant ID and object ID.

For a persistent environment, run migrations before starting the API:

```bash
alembic upgrade head
```

Run the API:

```bash
uvicorn src.main:app --reload
```

Run the independent worker in another process:

```bash
python -m src.workers.ingestion_worker
```

Queue an incremental historical backfill without keeping a web request open:

```bash
python -m scripts.enqueue_directory path/to/customer-export --workspace athletics-finance --max-files 10000
```

This operator command assumes trusted database/storage credentials. It handles
new and changed files; source deletion and upstream checkpoints remain separate
customer-policy work.

Open the interactive docs:

```text
http://localhost:8000/docs
```

Review queue:

```text
GET /statements/review?status=needs_review
```

Submit a review decision with `review.write` permission:

```text
POST /statements/review/{document_id}/decision
GET  /statements/review/{document_id}/history
```

Approval accepts an `expected_review_version` and optional record-level field
corrections. Required fields must be complete before publication; rejection and
every correction are recorded with the authenticated actor and audit snapshot.

---

## API Example

### `POST /ingestions`

Upload a document using `multipart/form-data` with a `file` field and two required headers:

```text
X-Tenant-ID: athletics-finance
X-User-ID: local-developer
Idempotency-Key: source-system-123-version-4
```

The endpoint returns `202 Accepted` immediately after the source and job are durable:

```json
{
  "job_id": "891fbc18-28d9-4a38-948d-78430250e0bf",
  "tenant_id": "athletics-finance",
  "idempotency_key": "source-system-123-version-4",
  "filename": "contract.pdf",
  "status": "queued",
  "processing_stage": null,
  "attempt_count": 0,
  "max_attempts": 3,
  "document_id": null
}
```

Poll `GET /ingestions/{job_id}`. Operators can inspect tenant-scoped queue depth
and oldest queued work at `GET /ingestions/operations/summary`. Failed jobs can
be replayed with `POST /ingestions/{job_id}/retry`.

`POST /statements/upload` remains available as a deprecated synchronous route
for compatibility and local comparison; it is not the scale path.

---

## Architecture Notes And Next Steps

The remaining production blockers are deliberately visible:

- Entra JWT validation and membership-backed authorization are implemented and unit-tested; a real app registration and multi-user cloud test remain required before claiming deployed identity integration.
- The three-case recorded regression suite passes, but the project explicitly fails its 50-case pilot-readiness minimum until approved or public ground truth exists.
- PostgreSQL concurrency and end-to-end Docling/model throughput have not been load-tested. The checked-in synthetic benchmark tests only the job state machine.
- Policy-driven data deletion remains an open customer workflow decision; human correction and approval are now implemented, but require a real multi-reviewer cloud test.

Run the deterministic checks:

```bash
python -m pytest -q
python evals/run_eval.py
python -m scripts.simulate_ingestion_load --jobs 1000
```

After downloading the official CUAD `data.zip` outside the repository, reproduce
the public retrieval baseline:

```bash
python -m evals.run_cuad_retrieval_eval --cuad-zip path/to/data.zip --top-k 5
```

The checked-in 2026-09-06 result covers all 510 contracts and 2,292 positive
queries across document name, parties, agreement date, effective date, and
expiration date. BM25 evidence recall@5 was `80.50%`. This is a retrieval
baseline, not an end-to-end extraction accuracy claim. See
`docs/DATASET_CARD_CUAD.md` and the JSON evidence artifact for category-level
results.

See `docs/PRODUCTION_REVIEW.md` for the current customer deployment brief, acceptance criteria, gap register, assumption register, and architecture decision log.

See `docs/HARNESS_ENGINEERING.md` for the text data lifecycle, chunking contract, retrieval behavior, context assembly design, and evaluation metrics.

See `docs/THREAT_MODEL.md` for the identity, tenant, source storage, model, worker,
and review trust boundaries and their remaining risks.

See `docs/PORTFOLIO_CASE_STUDY.md` for the customer-to-implementation narrative,
evidence-backed resume bullets, and interview walkthrough.

---

## Public Repository Note

Do not commit `.env` files, API keys, private documents, or real user/customer data. This repository is intended to show the architecture and implementation pattern, not private source documents.
