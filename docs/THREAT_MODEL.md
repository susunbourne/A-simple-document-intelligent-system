# Document Intelligence Threat Model

## Protected Assets

- Original contracts, statements, scans, and extracted text.
- Embeddings and chunks that can reveal source content.
- Structured financial and contractual records.
- Entra access tokens and workspace memberships.
- Model credentials, Blob permissions, and database credentials.
- Review decisions and source provenance.

## Identity Path

```text
Entra issues signed access token
  -> API validates signature, issuer, audience, expiration, tid, and oid
  -> X-Tenant-ID selects a data workspace
  -> backend requires active membership for token tid + oid
  -> role permission authorizes ingest/read/retry/operations/review
  -> every data query includes workspace_id
```

Changing `X-Tenant-ID` alone cannot grant access. Development mode accepts
`X-User-ID` and must never be enabled on an internet-facing deployment.

## Threats And Controls

| Threat | Control | Residual risk/status |
|---|---|---|
| Cross-workspace job or review access | Membership-backed authorization and tenant filters | Unit-tested; real multi-user cloud test open |
| Forged Entra token | JWKS signature, issuer, audience, expiry, `tid`, `oid` validation | Key retrieval/provider availability |
| Prompt injection inside document | System instruction treats document as untrusted, delimited user context, structured schema | Model behavior still requires adversarial eval |
| Raw source leaked through logs | Filename hash, metadata-only events, sanitized worker errors | Operator debug exports need future policy |
| Filename leaks through Blob path | Tenant hash + content hash object key | Storage admins can still access content by role |
| API/worker crash loses work | Durable source + PostgreSQL job + lease recovery | PostgreSQL/Blob outage behavior needs cloud test |
| Stale worker publishes after lease loss | Lease token required for completion; unique ingestion-job document lineage | External model call may still incur duplicate cost |
| Two reviewers overwrite each other | Row lock plus expected review version | Requires PostgreSQL integration test under real concurrency |
| Reviewer changes arbitrary database fields | Form-specific editable-field allowlists and Pydantic type validation | Business-format validation needs customer rules |
| Review has no accountable actor | Membership identity/role and before/after snapshot persisted per decision | Audit retention and export policy remain open |
| Client retry creates duplicate record | Tenant-scoped idempotency key; conflicting bytes return 409 | Upstream must provide stable source/version key |
| Oversized upload exhausts memory/disk | Streaming limit and bounded temporary spool | Direct-to-Blob needed above pilot limit |
| Deleted source remains in derived stores | No implemented retention/purge workflow | High open risk pending customer policy |
| External model receives restricted data | Explicit deployment assumption and selected context only | Requires customer approval/residency decision |

## Security Verification Still Required

- Deploy an actual Entra app registration and test owner, reviewer, suspended
  member, wrong tenant, wrong audience, expired token, and workspace switching.
- Verify API and worker Managed Identities have only required Blob and database
  access.
- Add adversarial documents that contain extraction overrides, fake system
  prompts, data-exfiltration requests, and oversized/recursive parser payloads.
- Define and test retention, legal hold, deletion, and backup purge semantics.
