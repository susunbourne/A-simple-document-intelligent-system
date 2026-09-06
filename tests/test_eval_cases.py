from pathlib import Path

from evals.validate_cases import validate_cases


def test_eval_sample_cases_are_valid():
    failures = validate_cases(Path("evals/sample_cases.json"))

    assert failures == {}
