# Text Data Contract

This contract defines the internal data objects that move through the document extraction harness.

## Parsed Document

Produced by `DoclingService`.

| Field | Type | Meaning |
|---|---|---|
| `filename` | string | Original uploaded filename |
| `raw_text` | string | Markdown-like text extracted from the source file |
| `content_sha256` | string | Hash of parsed text used for identity and deduplication analysis |

Rules:

- Raw text is allowed inside the parser, RAG, and document service.
- Raw text must not be printed to logs.
- Raw text should not be duplicated into every extraction table.

## Document Chunk

Produced by `RAGService.chunk_text_with_metadata`.

| Field | Type | Meaning |
|---|---|---|
| `chunk_id` | integer | Stable chunk number within one parsed document |
| `text` | string | Chunk content |
| `char_start` | integer | Start offset in parsed text |
| `char_end` | integer | End offset in parsed text |
| `token_estimate` | integer | Approximate context budget cost |
| `section_index` | integer | Logical section/chunk order |
| `embedding` | list[float] | Vector representation used for retrieval |

Rules:

- Chunks must preserve enough metadata to explain where context came from.
- Token estimate is approximate; it is for budgeting and comparison, not billing.
- Future page numbers or layout coordinates should be added here, not hidden in prompts.

## Retrieval Result

Produced by `RAGService.retrieve`.

| Field | Type | Meaning |
|---|---|---|
| `retrieval_query` | string | Query used for task-specific retrieval |
| `source_chunk_ids` | list[int] | Chunks selected for context |
| `scores` | object | Similarity score by chunk ID |
| `context` | string | Model-ready context with chunk metadata |

Rules:

- Retrieval quality must be evaluated separately from extraction quality.
- A correct extracted field without supporting retrieved evidence is not enough.

## Assembled Context

Produced by `ContextAssembler`.

| Field | Type | Meaning |
|---|---|---|
| `text` | string | Final context sent to the extraction model |
| `source_chunk_ids` | list[int] | Included chunks |
| `total_token_estimate` | integer | Estimated context size |
| `dropped_chunk_ids` | list[int] | Retrieved chunks excluded by budget |

Rules:

- Context budget must be explicit.
- Dropped chunks must be observable so retrieval failures are diagnosable.

## Extraction Record

Produced by specialized extraction services and persisted by service layer.

Common metadata:

| Field | Type | Meaning |
|---|---|---|
| `document_id` | integer | Source document row |
| `source_chunk_ids` | string | JSON list of chunks used as evidence |
| `processing_status` | string | `completed` or `needs_review` |
| `review_reason` | string/null | Missing fields or other review trigger |
| `router_confidence` | float/null | Document type confidence |

Rules:

- Missing required business fields should not be marked completed.
- Review status is a first-class output, not an exception string.

## Human Review Decision

Produced by `ReviewService` after an authorized reviewer acts on a
`needs_review` document.

| Field | Type | Meaning |
|---|---|---|
| `decision_id` | UUID | Immutable decision identity |
| `document_id` | integer | Reviewed document |
| `tenant_id` | string | Workspace boundary copied into the audit row |
| `action` | string | `approve` or `reject` |
| `actor_subject` | string | Stable identity-provider object ID |
| `actor_role` | string | Membership role used for authorization |
| `corrections` | JSON | Submitted allowlisted field changes |
| `before_snapshot` | JSON | Structured values before the decision |
| `after_snapshot` | JSON | Structured values after the decision |

Rules:

- Approval is rejected while required fields remain empty.
- `expected_review_version` prevents a stale browser or second reviewer from
  overwriting a newer decision.
- Review history queries include both `tenant_id` and `document_id`.
- Audit snapshots contain structured business values and therefore inherit the
  same retention and access policy as the source document.

## Evaluation Case

Stored in `evals/sample_cases.json`.

| Field | Type | Meaning |
|---|---|---|
| `sample_id` | string | Stable case ID |
| `document_type` | string | Expected router output |
| `source_text` | string | Synthetic or approved sample text |
| `expected` | object | Expected structured extraction |
| `expected_status` | string | Expected workflow status |
| `expected_evidence_terms` | list[string] | Terms that must appear in retrieved context |

Rules:

- Eval cases must not contain private documents.
- Evidence terms make context quality measurable.
