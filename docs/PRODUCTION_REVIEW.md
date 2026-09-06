# FDE Production Review

This review records the current evidence and boundaries of the document
intelligence engagement. The customer and workload are realistic training
assumptions, not a claim of paid customer work.

## Customer Deployment Brief

Assumed customer: a university athletics compliance and finance organization.
Analysts receive athlete agreements, sponsorship contracts, statements, and
supporting documents through email and departmental systems. They manually read
them, rekey fields, and ask a second employee to check ambiguous records.

The customer would pay to reduce review time while preserving evidence for
financial and contractual decisions. Incorrect amounts, dates, parties, or
tenant leakage could create reporting, compliance, privacy, and contractual
risk. A silent partial ingestion is more dangerous than a visible review item.

Assumed environment:

- Microsoft Entra ID and Azure are the likely enterprise control plane.
- PostgreSQL is the structured system of record.
- Private Blob Storage holds source documents.
- Existing upstream email and records systems cannot be replaced in the pilot.
- Pilot volume is 2,000 historical documents and 50 new documents/day.
- Department target is 200,000 documents and 2,000/day with bursty intake.
- Exact SLO, retention, residency, and cost ceilings require customer approval.

## Current-State Classification

Implemented:

- FastAPI synchronous compatibility endpoint and asynchronous `202` intake API.
- Bounded directory backfill connector with stable source-version keys for
  replay-safe historical ingestion.
- Streaming size enforcement and content-addressed source persistence.
- Local source adapter and private Azure Blob adapter using workload identity.
- PostgreSQL ingestion jobs with tenant-scoped idempotency keys.
- Independent worker with lease ownership, retries, exponential backoff, crash
  recovery, progress stages, and stale-owner protection.
- Docling parsing, document routing, paragraph chunking with offsets, OpenAI
  embeddings, top-k retrieval, explicit context budget, and structured outputs.
- Durable document/chunk records, source evidence, review status, and model/
  pipeline lineage.
- Human correction/approval/rejection with field allowlists, required-field
  gates, optimistic review versions, actor identity, and before/after audit.
- Stable application errors, request IDs, privacy-safe logs, readiness checks,
  Alembic migrations, deterministic tests, and recorded evaluation runner.

Partially implemented:

- Evaluation: a public CUAD retrieval baseline covers 510 contracts and 2,292
  positive evidence queries; end-to-end extraction still has only three recorded
  cases and explicitly does not pass the 50-case pilot minimum.
- Identity deployment: Entra JWT validation and membership-backed authorization
  are implemented and tested, but a real app registration/second-user flow has
  not been deployed for this project.
- Scale evidence: the job state machine has a 1,000-job synthetic SQLite run;
  PostgreSQL concurrency and end-to-end model throughput remain unmeasured.

Designed but not implemented:

- Entra app registration deployment and durable access audit events.
- Direct-to-Blob upload for files larger than the API upload limit.
- Policy-driven retention, deletion, legal hold, and source/chunk purge.
- PostgreSQL load test, end-to-end latency/cost telemetry, SLO dashboard/alerts.
- Connector checkpoints and deletion events for SharePoint/email ingestion.

Do not build without a requirement:

- Persistent vector database for a workflow that retrieves only within one
  uploaded document.
- Kafka, Kubernetes, service mesh, or multi-agent orchestration.
- Provider failover before the customer defines availability and residency
  requirements.

## Actual Data Flow

1. Client supplies a file, tenant context, and idempotency key.
2. API streams and hashes bytes into content-addressed source storage.
3. API commits an ingestion job and returns `202 Accepted` plus `job_id`.
4. Worker claims eligible work using a time-limited lease.
5. Docling parses the source into Markdown-like text.
6. Router classifies the document and applies the confidence gate.
7. The workflow creates chunks with offsets, embeds them, retrieves task-specific
   evidence, and assembles context under a token budget.
8. A specialized extractor returns Pydantic-validated structured output.
9. One transaction publishes document, chunk, evidence, and business records.
10. The lease owner marks the job completed; incomplete fields become review
    records, and retryable dependency failures use bounded backoff.

## Trust Boundaries

- Upload boundary: filenames, bytes, MIME claims, and idempotency keys are
  untrusted.
- Tenant boundary: `X-Tenant-ID` selects a workspace but does not grant access;
  the backend validates Entra `tid`/`oid` and active membership before querying.
- Parser boundary: Docling receives malformed or adversarial documents.
- Model boundary: selected text leaves the service for OpenAI processing.
- Storage boundary: API and worker identities require private Blob access.
- Review boundary: extracted values remain untrusted until validation and any
  customer-required human approval complete.

## Production Acceptance Criteria

Current engineering gates:

| Area | Target | Current evidence |
|---|---|---|
| Queue correctness | No duplicate job for same tenant/idempotency key | Automated tests |
| Crash recovery | Expired lease recoverable; stale worker cannot complete | Automated tests |
| Partial publication | One transactional business write | Workflow tests |
| Data leakage | No raw text in normal logs/job error record | Tests and code review |
| Schema evolution | Empty database migrates to current head | Alembic smoke |
| Retrieval baseline | Evidence recall@5 on public CUAD | 80.50% over 2,292 positive queries |
| Regression quality | Recorded extraction gate thresholds pass | 3 cases pass |
| Pilot quality | At least 50 representative labeled cases pass | Not met |
| Scale | PostgreSQL + Blob + model p95 under agreed workload | Not measured |
| Authorization | Entra claim + membership + negative cross-workspace tests | Implemented in code; cloud test open |
| Human approval | Missing fields cannot be approved; stale/cross-tenant decisions rejected | Automated tests and audit snapshots |

No availability, latency, accuracy, or monthly-cost promise is approved until a
customer supplies a representative corpus and policy.

## Engineering Gap Register

| Gap | Evidence | Severity | Category | Required action | Status |
|---|---|---:|---|---|---|
| Synchronous request owned long model work | Original `/statements/upload` ran full workflow | Critical | Must Implement | Durable source, job, lease, worker, retry | Implemented; old route deprecated |
| Worker crash could duplicate or lose processing | No durable job identity or lease existed | Critical | Must Implement | Lease recovery and unique job-to-document lineage | Implemented/tested |
| Local disk prevented independent cloud workers | Source bytes existed only in request memory | High | Must Implement | Pluggable private Blob source store with workload identity | Implemented adapter; cloud deployment unverified |
| Workspace selector could be mistaken for authorization | Caller supplies `X-Tenant-ID` | Critical | Must Implement Before Multi-user | Validate Entra token and resolve membership server-side | Implemented/tested; app registration deployment open |
| End-to-end extraction set is too small | Three recorded extraction cases; CUAD currently evaluates retrieval only | High | Must Implement Before Pilot | Create at least 50 representative extraction cases with field-level ground truth | Open; pilot gate correctly fails |
| Semantic retrieval is not benchmarked | BM25 recall@5 is 80.50%; Agreement Date is 58.30% | High | Must Implement | Evaluate current embedding retrieval on the same CUAD slice and beat the baseline without violating cost limits | Open; measured baseline exists |
| End-to-end scale is unmeasured | Only synthetic SQLite control-plane benchmark exists | High | Must Implement Before Scale Claim | Test PostgreSQL, Blob, Docling, models, latency, error rate, and cost | Open |
| Human review cannot correct/approve | Original review list was read-only | Medium | Must Implement Before Consequential Use | Add field correction, approval/rejection, actor, timestamp, concurrency control | Implemented/tested |
| Retention/deletion policy unknown | Source, chunks, and extracted records persist | High | Must Understand | Customer defines retention, legal hold, and purge semantics | Open |
| Cross-document vector store | Current extraction retrieves inside one document | Low | Do Not Build | Add only for evidence-backed historical search requirement | Deferred |

## Assumption Register

| Assumption | Why it matters | Revisit condition |
|---|---|---|
| Each extraction uses one source document | Justifies in-memory per-document vectors | Cross-document questions or re-indexing dominate cost |
| OpenAI may receive selected document text | Enables current router/embedding/extraction | Customer prohibits external processing or requires residency |
| 15 MiB API upload limit covers pilot | Allows bounded streaming through API | Scans exceed limit or concurrent upload pressure rises |
| PostgreSQL queue is adequate | Avoids operating a separate broker | Lock contention or queue latency misses measured SLO |
| Review is acceptable for uncertain output | Prevents silent false completion | Customer demands full automation or strict rejection |
| Source systems can provide stable idempotency keys | Enables safe replay | Email/manual sources cannot identify versions reliably |

## Architecture Decision Log

### ADR-001: PostgreSQL Queue Before A Separate Broker

The pilot already requires PostgreSQL transactions and modest intake. A leased
job table provides durability, retries, and worker coordination without a new
operational system. Revisit when measured lock contention, queue delay, or fanout
requires a broker. Kafka is not justified by current evidence.

### ADR-002: Content-Addressed Private Source Storage

The API must make bytes durable before accepting a job. Content hashing provides
storage idempotency and avoids filenames in object paths. Local and Blob adapters
share one contract; Azure uses workload identity instead of stored account keys.

### ADR-003: Keep Single-Document Retrieval

The current business output is structured extraction from one uploaded source.
A distributed vector store would add cost and authorization surface without
improving that requirement. Revisit for cross-document research, persistent
semantic search, or measured re-embedding cost.

### ADR-004: Separate Regression Gate From Pilot Readiness

Three recorded samples can detect accidental code changes but cannot establish
production quality. The runner reports the existing regression gate separately
and requires at least 50 representative cases for pilot readiness.

## Highest-Leverage Next Actions

1. Deploy the Entra app registration and prove a real owner/reviewer negative
   cross-workspace test with two identities.
2. Run the embedding retriever on the same CUAD slice, diagnose weak date
   categories, then build a 50+ case extraction gold set with layout diversity.
3. Run an end-to-end PostgreSQL/Blob/model load test and derive SLO and cost
   limits from evidence rather than invented targets.

## Senior FDE Review

| Capability | Rating | Evidence and limit |
|---|---|---|
| Requirement discovery | Production aware | Customer risk was translated into durability, review, identity, and evidence behavior; actual stakeholder interviews remain simulated |
| Data engineering | Production aware | Durable source lifecycle, versioned backfill, lineage, validation, and replay exist; upstream checkpoints/deletion remain open |
| AI engineering | Production aware | Retrieval and extraction are separated and versioned; public retrieval evidence exists, but the end-to-end gold set is too small |
| Security | Production aware | Signed-token design, membership RBAC, tenant filters, negative tests, and a threat model exist; no deployed Entra two-user evidence yet |
| Reliability | Production aware | Idempotency, leases, stale-owner protection, retries, and recovery are tested; cloud dependency behavior is unmeasured |
| Observability | Can implement | Structured request/job events and queue summaries exist; traces, cost metrics, dashboards, and alerts do not |
| Cloud/infrastructure | Can implement | Blob workload-identity adapter and migrations exist; this repository has not been deployed and load-tested in Azure |
| Engineering judgment | Production aware | PostgreSQL queue and single-document retrieval are defended against premature broker/vector-store complexity |

The project is now a credible FDE portfolio case because it connects a messy
customer workflow to concrete system behavior and admits the boundaries of its
evidence. It is not evidence of owning a five-million-document production
deployment, and the resume must not imply that claim.
