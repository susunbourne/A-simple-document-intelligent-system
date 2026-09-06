# Ingestion Operations Runbook

## Scope

Use this runbook when documents remain queued, jobs retry repeatedly, a worker
dies, source content is unavailable, or customers report missing results.

## First Five Minutes

1. Record tenant, `job_id`, request ID, customer-visible status, and impact.
2. Query `GET /ingestions/{job_id}` using an authorized tenant context.
3. Query `GET /ingestions/operations/summary` and compare queued, processing,
   retrying, completed, and failed counts.
4. Search structured logs by `job_id` or request ID. Do not ask the customer to
   paste private document text into a ticket.
5. Stop manual re-uploads until the idempotency key and source version are known.

## Diagnosis

| Observation | Likely layer | Check |
|---|---|---|
| `queued`, no worker activity | Worker/runtime | Worker process health and database connectivity |
| `processing`, lease expired | Worker crash/hang | Last `processing_stage`, worker logs, provider latency |
| `retry_wait` | Dependency | Error code, attempt count, next attempt, provider/Blob health |
| `failed: document_parse_failed` | Source/parser | File type, corruption, scan/OCR support |
| `failed: source_object_missing` | Storage/data integrity | Blob/local object existence and retention action |
| `needs_review` | Business quality | Missing fields and selected source chunk evidence |
| Repeated 409 | Client integration | Same idempotency key reused for different bytes |

## Mitigation

- Restarting a worker is safe; expired leases are recoverable.
- Do not edit a processing job to `completed` manually.
- Retry a terminal job through `POST /ingestions/{job_id}/retry` only after the
  dependency or source problem is understood.
- For a corrupt or unsupported source, upload a corrected version with a new
  idempotency key.
- If queue age rises while workers are healthy, reduce intake or add workers
  only after checking database lock time and provider rate limits.

## Verification

A recovery is complete only when:

- queue age returns to the accepted baseline;
- the affected job reaches `completed`, `needs_review`, or an explained terminal
  failure;
- exactly one document is linked to the ingestion job;
- selected source chunks and model/pipeline versions are present;
- no stale worker can overwrite the recovered result.

## Escalation Evidence

Provide job/request IDs, timestamps, status transitions, stage, attempt count,
provider status, and sanitized exception type. Never include raw document text,
access tokens, Blob SAS URLs, or API keys.
