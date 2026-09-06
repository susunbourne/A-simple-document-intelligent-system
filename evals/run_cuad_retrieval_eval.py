import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

from src.services.rag_service import LexicalRetriever, RAGService


def load_cuad(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open("CUADv1.json") as source:
            return json.load(source)


def answer_is_in_chunks(answer: dict, selected_chunks) -> bool:
    answer_text = str(answer.get("text") or "").strip()
    answer_start = int(answer.get("answer_start") or 0)
    answer_end = answer_start + len(answer_text)
    return any(
        (
            chunk.char_start <= answer_start
            and chunk.char_end >= answer_end
        )
        or (answer_text and answer_text in chunk.text)
        for chunk in selected_chunks
    )


def evaluate(
    zip_path: Path,
    *,
    top_k: int,
    limit: int | None,
    categories: set[str] | None = None,
) -> dict[str, object]:
    dataset = load_cuad(zip_path)
    contracts = dataset["data"][:limit] if limit else dataset["data"]
    chunker = RAGService.__new__(RAGService)
    retriever = LexicalRetriever()
    total = 0
    hits = 0
    category_totals = Counter()
    category_hits = Counter()

    for contract in contracts:
        for paragraph in contract["paragraphs"]:
            context = paragraph["context"]
            chunks = chunker.chunk_text_with_metadata(context)
            lexical_index = retriever.build_index(chunks)
            for item in paragraph["qas"]:
                answers = item.get("answers") or []
                if not answers:
                    continue
                category = item["question"].split('"')[1]
                if categories and category not in categories:
                    continue
                result = retriever.retrieve_index(lexical_index, item["question"], top_k=top_k)
                hit = any(answer_is_in_chunks(answer, result.source_chunks) for answer in answers)
                total += 1
                hits += int(hit)
                category_totals[category] += 1
                category_hits[category] += int(hit)

    by_category = {
        category: {
            "cases": category_totals[category],
            "hits": category_hits[category],
            "recall_at_k": round(category_hits[category] / category_totals[category], 4),
        }
        for category in sorted(category_totals)
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "Contract Understanding Atticus Dataset v1",
        "dataset_license": "CC BY 4.0",
        "dataset_url": "https://www.atticusprojectai.org/cuad/",
        "retriever": "deterministic_bm25_baseline",
        "top_k": top_k,
        "categories": sorted(categories) if categories else "all",
        "contract_count": len(contracts),
        "positive_query_count": total,
        "hits": hits,
        "evidence_recall_at_k": round(hits / total, 4) if total else 0.0,
        "includes_model_calls": False,
        "by_category": by_category,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate retrieval against CUAD answer spans.")
    parser.add_argument("--cuad-zip", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--categories",
        default="Document Name,Parties,Agreement Date,Effective Date,Expiration Date",
        help="Comma-separated CUAD categories; use 'all' for every category.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    categories = None
    if args.categories.strip().lower() != "all":
        categories = {item.strip() for item in args.categories.split(",") if item.strip()}
    result = evaluate(
        args.cuad_zip,
        top_k=args.top_k,
        limit=args.limit,
        categories=categories,
    )
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
