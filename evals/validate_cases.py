import json
from pathlib import Path


REQUIRED_TOP_LEVEL_FIELDS = {
    "sample_id",
    "document_type",
    "source_text",
    "expected",
    "expected_status",
    "expected_evidence_terms",
}
ALLOWED_DOCUMENT_TYPES = {"bank_statement", "athlete_contract", "unknown"}
ALLOWED_STATUSES = {"completed", "needs_review", "rejected"}


def validate_case(case: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL_FIELDS - set(case)
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
    if case.get("document_type") not in ALLOWED_DOCUMENT_TYPES:
        errors.append(f"invalid document_type: {case.get('document_type')}")
    if case.get("expected_status") not in ALLOWED_STATUSES:
        errors.append(f"invalid expected_status: {case.get('expected_status')}")
    if not str(case.get("source_text") or "").strip():
        errors.append("source_text must not be empty")
    if not isinstance(case.get("expected_evidence_terms"), list):
        errors.append("expected_evidence_terms must be a list")
    if case.get("document_type") == "bank_statement" and "statements" not in case.get("expected", {}):
        errors.append("bank_statement cases must include expected.statements")
    if case.get("document_type") == "athlete_contract" and "contracts" not in case.get("expected", {}):
        errors.append("athlete_contract cases must include expected.contracts")
    if case.get("document_type") == "unknown" and case.get("expected_status") != "rejected":
        errors.append("unknown document cases must be rejected")
    return errors


def validate_cases(path: Path) -> dict[str, list[str]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    failures: dict[str, list[str]] = {}
    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        sample_id = str(case.get("sample_id") or f"case_{index}")
        errors = validate_case(case)
        if sample_id in seen_ids:
            errors.append("duplicate sample_id")
        seen_ids.add(sample_id)
        if errors:
            failures[sample_id] = errors
    return failures


def main() -> int:
    path = Path(__file__).with_name("sample_cases.json")
    failures = validate_cases(path)
    if failures:
        print(json.dumps(failures, indent=2))
        return 1
    print(f"Validated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
