# FDE AI Data Harness Engineering

This project is primarily the AI data-layer workstream of a Forward-Deployed Engineering engagement. The goal is to show how a customer's raw, inconsistent documents become controlled model inputs, structured outputs, measurable extraction quality, and auditable evidence.

The FDE responsibility represented here is translating an ambiguous customer workflow into a concrete data contract and an AI automation pipeline that can be inspected, tested, and improved. Durable intake, worker recovery, and private cloud source storage are implemented; identity-bound authorization and a measured cloud deployment remain explicit production blockers.

## Core Problem

The hard part is not calling an LLM. The hard part is managing text data so the model receives the right context and the system can prove why a field was extracted.

For bank statements and athlete contracts, the system must answer:

- What source text did we actually extract from the file?
- How was that text divided into chunks?
- Which chunks were retrieved for this document type?
- What exact context reached the model?
- Which fields were extracted?
- Which fields were missing or unsupported?
- Did the retrieved context contain evidence for the expected answer?
- Can we reproduce and evaluate the behavior after a prompt, model, or chunking change?

## Text Data Lifecycle

```text
source file + idempotency key
  -> content-addressed private source storage
  -> durable leased ingestion job
  -> independent worker
  -> parser
  -> normalized markdown text
  -> chunking with offsets
  -> embeddings
  -> retrieval query
  -> ranked chunks
  -> context assembly under token budget
  -> structured extraction
  -> field validation
  -> evidence-linked persistence
  -> evaluation harness
```

## Concrete Components

### Durable Intake

Implemented in:

- `src/api/ingestion.py`
- `src/repositories/ingestion_repository.py`
- `src/services/object_store.py`
- `src/services/ingestion_service.py`
- `src/workers/ingestion_worker.py`

The API returns only after both source bytes and the job are durable. Workers
claim jobs with time-limited leases, report processing stage through heartbeats,
retry transient failures with bounded exponential backoff, and cannot complete
work after losing lease ownership.

### Parser

Implemented in `src/services/docling_service.py`.

Input:

- uploaded file bytes
- filename

Output:

- Markdown-like text
- extracted character count in logs

Constraint:

- raw parsed text is not printed to logs or written to `output.md`

### Chunking

Implemented in `src/services/rag_service.py`.

Each chunk stores:

- `chunk_id`
- `text`
- `char_start`
- `char_end`
- `token_estimate`
- `section_index`

Why this matters:

- `chunk_id` gives retrieval provenance.
- character offsets make it possible to trace a chunk back to source text.
- token estimates support explicit context budgeting.
- section indexes help compare future paragraph, page, section, or clause-based chunking strategies.

### Retrieval

Implemented in `src/services/rag_service.py`.

Current retrieval behavior:

- embed every chunk with `text-embedding-3-small`
- embed a task-specific retrieval query
- rank chunks by cosine similarity
- return top-k chunks with score metadata

Document-type retrieval queries:

- bank statement: transaction descriptions, dates, debits, credits, deposits, amounts
- athlete contract: parties, dates, term, compensation, contract value, currency

### Context Assembly

Implemented in `src/services/context_service.py`.

The assembler enforces a context token budget and records:

- included chunk IDs
- dropped chunk IDs
- total estimated context tokens
- chunk metadata in the final context text

Why this matters:

- context is an engineered artifact, not a random string concat
- token budget is explicit
- dropped chunks are observable
- model input can be inspected during eval

### Structured Extraction

Implemented in:

- `src/services/extraction_service.py`
- `src/agents/contract_agent.py`

Extraction uses OpenAI structured outputs with Pydantic schemas. Missing required business fields are not treated as completed records; they become `needs_review`.

### Evidence-Linked Persistence

Implemented in:

- `src/models/document.py`
- `src/models/statement.py`
- `src/models/athlete_contract.py`
- `src/services/document_service.py`

The system stores:

- document metadata and content hash
- durable document chunks
- extraction records linked to `document_id`
- selected `source_chunk_ids`
- `processing_status`
- `review_reason`

## Evaluation Harness

Implemented in `evals/`.

The recorded eval currently measures:

- `router_accuracy`
- `status_accuracy`
- `field_accuracy`
- `evidence_coverage`

`evidence_coverage` checks whether retrieved context contains expected evidence terms. This is intentionally separate from field accuracy because a model can sometimes guess a correct field from weak or incomplete context.

Run:

```bash
python evals/run_eval.py
```

Quality gate:

- router accuracy >= 95%
- status accuracy = 100%
- field accuracy >= 90%
- evidence coverage >= 90%

## What This Project Should Demonstrate

Strong signal:

- unstructured text parsing
- chunk metadata design
- retrieval query design
- context budget management
- structured model output
- missing-field handling
- source evidence tracking
- deterministic evaluation harness

Not the main signal right now:

- Kubernetes
- Kafka
- complex multi-agent orchestration
- enterprise identity
- distributed vector databases

Those may matter in a later deployment project. They are not required to prove text-data harness engineering.
