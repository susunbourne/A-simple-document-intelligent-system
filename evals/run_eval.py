import argparse
import json
from pathlib import Path
from typing import Any


ROUTER_ACCURACY_THRESHOLD = 0.95
FIELD_ACCURACY_THRESHOLD = 0.90
STATUS_ACCURACY_THRESHOLD = 1.0
EVIDENCE_COVERAGE_THRESHOLD = 0.90
PILOT_MIN_CASE_COUNT = 50


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_fields(payload: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for collection_name, records in payload.items():
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            for field_name, value in record.items():
                flattened[f"{collection_name}.{index}.{field_name}"] = value
    return flattened


def score_eval(cases: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    predictions_by_id = {prediction["sample_id"]: prediction for prediction in predictions}
    router_correct = 0
    status_correct = 0
    field_correct = 0
    field_total = 0
    evidence_correct = 0
    evidence_total = 0
    failures: list[dict[str, Any]] = []

    for case in cases:
        sample_id = case["sample_id"]
        prediction = predictions_by_id.get(sample_id)
        if prediction is None:
            failures.append({"sample_id": sample_id, "error": "missing prediction"})
            continue

        if prediction.get("predicted_document_type") == case["document_type"]:
            router_correct += 1
        else:
            failures.append(
                {
                    "sample_id": sample_id,
                    "error": "document_type_mismatch",
                    "expected": case["document_type"],
                    "actual": prediction.get("predicted_document_type"),
                }
            )

        if prediction.get("predicted_status") == case["expected_status"]:
            status_correct += 1
        else:
            failures.append(
                {
                    "sample_id": sample_id,
                    "error": "status_mismatch",
                    "expected": case["expected_status"],
                    "actual": prediction.get("predicted_status"),
                }
            )

        expected_fields = flatten_fields(case.get("expected", {}))
        predicted_fields = flatten_fields(prediction.get("predicted", {}))
        for field_name, expected_value in expected_fields.items():
            field_total += 1
            actual_value = predicted_fields.get(field_name)
            if actual_value == expected_value:
                field_correct += 1
            else:
                failures.append(
                    {
                        "sample_id": sample_id,
                        "error": "field_mismatch",
                        "field": field_name,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )

        retrieved_context = str(prediction.get("retrieved_context") or "")
        for term in case.get("expected_evidence_terms", []):
            evidence_total += 1
            if str(term) in retrieved_context:
                evidence_correct += 1
            else:
                failures.append(
                    {
                        "sample_id": sample_id,
                        "error": "missing_evidence_term",
                        "term": term,
                    }
                )

    total = len(cases)
    return {
        "router_accuracy": router_correct / total if total else 0,
        "status_accuracy": status_correct / total if total else 0,
        "field_accuracy": field_correct / field_total if field_total else 1.0,
        "evidence_coverage": evidence_correct / evidence_total if evidence_total else 1.0,
        "case_count": total,
        "field_count": field_total,
        "evidence_term_count": evidence_total,
        "failures": failures,
    }


def passes_gate(result: dict[str, Any]) -> bool:
    return (
        result["router_accuracy"] >= ROUTER_ACCURACY_THRESHOLD
        and result["status_accuracy"] >= STATUS_ACCURACY_THRESHOLD
        and result["field_accuracy"] >= FIELD_ACCURACY_THRESHOLD
        and result["evidence_coverage"] >= EVIDENCE_COVERAGE_THRESHOLD
    )


def passes_pilot_gate(result: dict[str, Any]) -> bool:
    return result["case_count"] >= PILOT_MIN_CASE_COUNT and passes_gate(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score recorded document-intelligence eval outputs.")
    parser.add_argument("--cases", default="evals/sample_cases.json")
    parser.add_argument("--predictions", default="evals/sample_predictions.json")
    args = parser.parse_args()

    result = score_eval(load_json(Path(args.cases)), load_json(Path(args.predictions)))
    result["recorded_regression_gate_passed"] = passes_gate(result)
    result["pilot_readiness_gate_passed"] = passes_pilot_gate(result)
    result["pilot_minimum_case_count"] = PILOT_MIN_CASE_COUNT
    print(json.dumps(result, indent=2))
    return 0 if passes_gate(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
