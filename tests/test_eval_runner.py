from pathlib import Path
import json
import zipfile

from evals.run_eval import load_json, passes_gate, passes_pilot_gate, score_eval
from evals.run_cuad_retrieval_eval import evaluate


def test_recorded_eval_predictions_pass_quality_gate():
    result = score_eval(
        load_json(Path("evals/sample_cases.json")),
        load_json(Path("evals/sample_predictions.json")),
    )

    assert passes_gate(result)
    assert not passes_pilot_gate(result)
    assert result["failures"] == []


def test_cuad_retrieval_eval_scores_annotated_answer_span(tmp_path):
    context = "Background. The parties are Northwind LLC and Contoso Inc. End."
    answer = "Northwind LLC and Contoso Inc"
    payload = {
        "version": "test",
        "data": [
            {
                "title": "sample",
                "paragraphs": [
                    {
                        "context": context,
                        "qas": [
                            {
                                "question": 'Highlight parts related to "Parties". Details: parties',
                                "answers": [
                                    {"text": answer, "answer_start": context.index(answer)}
                                ],
                                "is_impossible": False,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    archive_path = tmp_path / "data.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("CUADv1.json", json.dumps(payload))

    result = evaluate(archive_path, top_k=1, limit=None, categories={"Parties"})

    assert result["positive_query_count"] == 1
    assert result["evidence_recall_at_k"] == 1.0
