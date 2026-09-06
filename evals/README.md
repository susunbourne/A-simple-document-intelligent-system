# Evaluation Baseline

This folder defines the first production-style quality gate for the document intelligence pipeline.

The goal is not to prove that the model is perfect. The goal is to prevent unmeasured changes to routing, retrieval, extraction prompts, schemas, or persistence behavior.

## Current Gate

Before a pilot deployment, the system must pass:

- Router classification accuracy >= 95% on labeled samples.
- Required field extraction accuracy >= 90% on labeled samples.
- Unsupported documents must not be persisted as completed records.
- Missing required fields must become `needs_review`, not a server crash.
- No raw document text may be written to application logs.

## Sample Contract

Each labeled sample should include:

- `sample_id`
- `document_type`
- `source_text`
- expected extracted fields
- expected behavior: `completed`, `needs_review`, or `rejected`

Use synthetic or explicitly approved documents only. Do not commit private bank statements, contracts, or customer data.

## Run The Recorded Eval

The current runner scores recorded predictions without calling a live LLM:

```bash
python evals/run_eval.py
```

This keeps CI deterministic. Add a separate live-model mode only when the team is ready to manage API cost, provider availability, and prompt/model versioning.

## Public CUAD Retrieval Baseline

`run_cuad_retrieval_eval.py` evaluates source-chunk recall against expert answer
spans from the CC BY 4.0 Contract Understanding Atticus Dataset. The source
archive is downloaded separately and is not committed to this repository.

```bash
python -m evals.run_cuad_retrieval_eval --cuad-zip path/to/data.zip --top-k 5
```

This benchmark measures retrieval only. It does not call an LLM and must not be
reported as extraction accuracy.
