# Document Intelligence Architecture

This folder contains the combined architecture diagram for the Document Intelligent System and instructions for exporting to PDF.

## Files
- `architecture.mmd` - Mermaid diagram source (single combined framework diagram).

## How to export to PDF or PNG
Recommended: use `@mermaid-js/mermaid-cli` (`mmdc`).

Install (Node.js required):

```bash
npm install -g @mermaid-js/mermaid-cli
```

Export to PNG:

```bash
mmdc -i docs/architecture.mmd -o docs/architecture.png -w 1600 -H 1200
```

Export to PDF:

```bash
mmdc -i docs/architecture.mmd -o docs/architecture.pdf
```

Alternative: open `docs/architecture.mmd` in VS Code with a Mermaid preview extension and export manually.

## Quick notes
- The diagram shows: Ingest -> Router -> Per-Agent workflow (pre-parse, chunking, retrieval, LLM extraction, verification) -> Persistence & Metrics.
- If you want, I can also generate a one-page PDF and commit it to the repo.
