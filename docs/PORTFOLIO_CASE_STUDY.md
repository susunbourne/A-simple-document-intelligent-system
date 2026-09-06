# Portfolio Case Study: Forward-Deployed Document Intelligence

## The Customer Problem

This project models a deployment for a university athletics compliance and
finance organization. Analysts receive contracts, statements, scans, and office
documents from multiple sources, manually rekey important fields, and ask a
second employee to resolve ambiguous results.

The engineering problem is not merely extracting JSON. The customer needs each
accepted file to survive process failure, each result to remain inside its
workspace, each field to retain source evidence, and each uncertain result to
enter an accountable human decision process.

This is a simulated customer brief used for engineering training. It is not a
claim of paid customer deployment.

## Requirement Discovery To System Behavior

| Customer concern | Operational requirement | Implemented behavior |
|---|---|---|
| Upload must not disappear | Bytes and work become durable before acknowledgement | Content-addressed source store + PostgreSQL job, then HTTP 202 |
| Client retries are common | Repeating one source/version must not duplicate work | Workspace-scoped idempotency key and content conflict detection |
| Parsing/model calls are slow | Web request cannot own long-running work | Independent leased worker with progress stages |
| Worker may crash | Work must be recoverable without stale publication | Lease expiry, retry/backoff, stale-token rejection, committed-result recovery |
| Departments must not see each other's files | Identity and data authorization must be connected | Entra claim validation + active workspace membership + tenant-filtered queries |
| Model output can be incomplete | Uncertain output must not silently become final | Required-field gates and `needs_review` state |
| Human correction is consequential | Decisions need concurrency control and audit | Allowlisted corrections, review version, actor/role, before/after snapshot |
| AI changes can regress quality | Releases need reproducible evidence | Recorded extraction gate + public CUAD retrieval benchmark |

## Architecture Decisions

The project deliberately uses a PostgreSQL job table instead of Kafka because
the assumed pilot already depends on PostgreSQL and has no measured queue
contention that justifies another operational system. It keeps retrieval within
one document instead of adding a vector database because the implemented task
is evidence-guided extraction, not enterprise search.

Azure Blob is available behind a storage interface for cloud deployment, while
local development uses the same content-addressed contract. The Azure adapter
uses workload identity rather than storing an account key in application
configuration.

These choices show evolutionary architecture: add a component when a measured
requirement needs it, not because it looks impressive in a diagram.

## Evidence

- `30` automated tests cover routing/workflow behavior, context budgeting,
  tenant authorization, idempotency, lease recovery, stale workers, privacy-safe
  logging, human review, and evaluation runners.
- Alembic upgrades an empty database through four revisions, including durable
  ingestion, workspace authorization, and review audit state.
- A deterministic control-plane run completed `1,000` synthetic jobs at about
  `1,019` enqueues/s and `305` claim-plus-terminal transitions/s on SQLite. This
  does not include parsing, cloud storage, PostgreSQL concurrency, or models.
- The official CUAD v1 corpus supplied `510` contracts and `2,292` positive
  schema-aligned evidence queries. The reproducible BM25 baseline achieved
  `80.50%` evidence recall@5 with no model calls. This is retrieval evidence,
  not end-to-end extraction accuracy.
- The three-case extraction regression set passes, while the pilot-readiness
  gate correctly remains false until at least `50` representative labeled cases
  exist.

## Resume Bullets

- Built a multi-tenant document intelligence control plane using FastAPI,
  PostgreSQL, Docling, and OpenAI structured outputs, with durable `202` intake,
  workspace-scoped idempotency, leased workers, bounded retries, and
  crash-safe result recovery.
- Implemented end-to-end authorization from Microsoft Entra token claims to
  server-side workspace membership and tenant-filtered data access, plus an
  auditable human review flow with allowlisted corrections and optimistic
  concurrency control.
- Created a reproducible retrieval evaluation against 510 public CUAD contracts
  and 2,292 positive evidence queries, establishing an 80.50% BM25 recall@5
  baseline and exposing date-field weaknesses before paid model experiments.
- Designed evidence-linked AI processing that preserves chunk hashes/offsets,
  selected context IDs, model lineage, review status, stable error codes, and
  privacy-safe operational logs.

Use these bullets only together with the stated evidence boundaries. Do not
describe the system as serving five million documents or meeting a production
SLO until the corresponding cloud load test exists.

## Interview Walkthrough

Start with the customer failure: a synchronous prototype could lose long-running
work, duplicate expensive model calls after client retries, and publish
incomplete values without a responsible reviewer. Then walk through one file:

1. Entra authenticates the user; the API resolves role and workspace membership.
2. The API streams and hashes the file into durable storage and commits one job.
3. A worker owns the job through a lease and reports processing stages.
4. Docling parses the source; the router gates unsupported or uncertain types.
5. Chunks retain offsets/hashes; retrieval selects evidence under a context
   budget; structured outputs are validated before persistence.
6. Missing fields become review work. An authorized reviewer corrects or rejects
   them through a versioned, auditable decision.
7. Evaluation separates component quality, end-to-end readiness, and operational
   throughput so one good demo cannot masquerade as production evidence.

Finish with the next experiment, not another technology: benchmark semantic
retrieval against the same CUAD slice, build a representative 50-case extraction
set, and measure PostgreSQL/Blob/model latency and cost under an agreed workload.
