# Durable Ingestion Control Plane

## Customer Requirement

The assumed customer is a university athletics compliance and finance team that
receives athlete agreements and supporting financial documents from multiple
source systems. Staff cannot keep an upload request open while OCR, retrieval,
and model extraction finish. A client retry must not create duplicate business
records, and a worker crash must not lose or silently publish partial work.

The organization and workload numbers are training assumptions, not claims of a
real customer deployment:

| Stage | Documents | Daily intake | Concurrent submissions |
|---|---:|---:|---:|
| Pilot | 2,000 | 50 | 5 |
| Department | 200,000 | 2,000 | 50 |
| Enterprise | 5,000,000 | 50,000 | 300 |

## Implemented Flow

```text
Bearer identity + authorized workspace + multipart upload + idempotency key
  -> stream and hash bytes
  -> private content-addressed source object
  -> commit PostgreSQL ingestion job
  -> return HTTP 202 + job_id
  -> worker claims job with a time-limited lease
  -> parse -> route -> chunk/embed -> retrieve -> extract -> validate
  -> commit document, chunks, evidence, and business records
  -> atomically mark job completed with document_id
```

If a worker stops after committing the document but before completing the job,
the next lease owner finds `documents.ingestion_job_id` and links the existing
result instead of running the model again. A stale worker cannot complete a job
after another worker owns its lease.

## Failure Semantics

| Failure | Behavior | Customer/Operator View |
|---|---|---|
| Same idempotency key, same bytes | Return existing job | Safe client retry |
| Same key, different bytes | HTTP 409 | Client must use a new source version/key |
| Unsupported or low-confidence document | Terminal failure/review boundary | Stable error code |
| Provider/transient worker error | Exponential retry up to configured maximum | `retry_wait`, attempt count, safe error type |
| Worker process dies | Lease expires and another worker can claim | Attempt count increases; no lost request |
| Durable source missing | Terminal `source_object_missing` | Regenerate/re-upload source |

Raw document text and exception messages are not persisted in the job error
record. This trades some debugging convenience for a safer default around bank
and contract content.

## Storage Decision

Local development uses a content-addressed directory. Cloud deployment uses the
same interface backed by a private Azure Blob container and
`DefaultAzureCredential`. API and worker identities need data-plane access to
that container; storage account keys are not an application configuration
option.

The source key contains a one-way tenant hash and content hash, not the original
filename. This limits accidental disclosure in object paths and makes duplicate
uploads storage-idempotent.

## Evidence And Boundary

On 2026-09-06:

- `30` automated tests passed.
- Alembic upgraded an empty SQLite database through revisions `0001`, `0002`, `0003`, and `0004`.
- A synthetic SQLite run enqueued and claimed/terminated all `1,000` jobs.
- The run measured about `1,019` enqueue jobs/s and `305` claim/terminal jobs/s.

That benchmark excludes file parsing, network storage, PostgreSQL locking, and
model calls. It proves state-machine behavior under repeated work; it is not an
end-to-end throughput or cloud capacity claim.
