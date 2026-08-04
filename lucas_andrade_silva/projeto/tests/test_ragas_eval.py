import json

import pytest

from rag.evaluation.ragas_eval import load_examples


def test_load_examples_reads_jsonl(tmp_path):
    path = tmp_path / "examples.jsonl"
    path.write_text(
        json.dumps({"question": "O que e NVIDIA NIM?", "ground_truth": "Servico NVIDIA."}),
        encoding="utf-8",
    )

    assert load_examples(path) == [
        {"question": "O que e NVIDIA NIM?", "ground_truth": "Servico NVIDIA."}
    ]


def test_load_examples_requires_question(tmp_path):
    path = tmp_path / "examples.jsonl"
    path.write_text(json.dumps({"ground_truth": "Sem pergunta."}), encoding="utf-8")

    with pytest.raises(ValueError, match="question"):
        load_examples(path)
