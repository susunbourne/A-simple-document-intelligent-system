# CUAD Retrieval Evaluation Dataset Card

## Purpose

The Contract Understanding Atticus Dataset (CUAD) is used only to evaluate
whether retrieval returns source chunks containing expert-annotated answer
spans. It does not establish the accuracy of this project's router or structured
extractor.

Official source: https://www.atticusprojectai.org/cuad/

Official code/data repository: https://github.com/TheAtticusProject/cuad

License: Creative Commons Attribution 4.0 (CC BY 4.0).

CUAD contains 510 commercial contracts, more than 13,000 expert labels, and 41
legal clause categories. The project does not commit or redistribute the source
archive. A user downloads `data.zip` from the official source and passes its path
to the evaluation command.

## Current Evaluation Slice

The first baseline selects categories that overlap with the implemented contract
schema:

- Document Name
- Parties
- Agreement Date
- Effective Date
- Expiration Date

Only questions with one or more annotated answer spans count toward evidence
recall. A hit occurs when at least one annotated answer falls inside one of the
top-k retrieved chunks.

## Reproduction

```bash
python -m evals.run_cuad_retrieval_eval \
  --cuad-zip path/to/data.zip \
  --top-k 5 \
  --output docs/evidence/cuad-510-contract-retrieval-baseline.json
```

## Recorded Baseline

Run date: 2026-09-06.

| Metric | Result |
|---|---:|
| Contracts | 510 |
| Positive queries | 2,292 |
| BM25 evidence recall@5 | 80.50% |
| Parties recall@5 | 97.25% |
| Document Name recall@5 | 83.14% |
| Expiration Date recall@5 | 85.71% |
| Effective Date recall@5 | 76.41% |
| Agreement Date recall@5 | 58.30% |

The large gap between Parties and Agreement Date is an actionable retrieval
finding. The next experiment is to score the existing embedding retriever on the
same queries and inspect misses before changing chunk size, query construction,
or model choice.

## Limitations

- CUAD contracts are commercial legal agreements, not private customer traffic.
- The archive represents text contexts and expert spans, not this system's full
  PDF/Docling/OCR path.
- The current run evaluates positive evidence recall, not false positives,
  ranking precision, extraction accuracy, latency, or cost.
- BM25 is an offline baseline; production currently uses OpenAI embeddings.
