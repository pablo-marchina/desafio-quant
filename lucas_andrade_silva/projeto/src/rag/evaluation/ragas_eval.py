from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_JUDGE_MODEL = "openai/gpt-oss-120b"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"

DEFAULT_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def load_examples(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not row.get("question"):
            raise ValueError(f"Linha {line_number} precisa conter question")
        rows.append(row)
    return rows


def build_ragas_rows(examples: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    from rag.generation.rag_query import build_context, generate_answer

    rows = []
    for example in examples:
        answer, chunks = generate_answer(
            str(example["question"]),
            service=example.get("service"),
            category=example.get("category"),
        )
        rows.append(
            {
                "question": str(example["question"]),
                "answer": answer,
                "contexts": [build_context(chunks)] if chunks else [],
                "ground_truth": str(example.get("ground_truth") or ""),
                "source_urls": list(dict.fromkeys(chunk["source_url"] for chunk in chunks)),
            }
        )
    return rows


def _metric_objects(metric_names: Iterable[str]):
    try:
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as error:
        raise RuntimeError(
            "Instale as dependencias de avaliacao com "
            "`pip install -r requirements/evaluation.txt`. "
            f"Falha original: {error}"
        ) from error

    available = {
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
        "faithfulness": faithfulness,
    }
    selected = []
    for name in metric_names:
        if name not in available:
            raise ValueError(f"Metrica RAGAS desconhecida: {name}")
        selected.append(available[name])
    return selected


def build_groq_judge(model_name: str):
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as error:
        raise RuntimeError(
            "Instale as dependencias de avaliacao com "
            "`pip install -r requirements/evaluation.txt`. "
            f"Falha original: {error}"
        ) from error

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY nao foi definida no arquivo .env. "
            "Ela e necessaria para usar Groq como LLM avaliadora do RAGAS."
        )

    return ChatOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        model=model_name,
        temperature=0,
        max_retries=2,
        timeout=60,
    )


def build_local_embeddings(model_name: str):
    try:
        import torch
        from FlagEmbedding import BGEM3FlagModel
    except ImportError as error:
        raise RuntimeError(
            "Instale as dependencias de avaliacao com "
            "`pip install -r requirements/evaluation.txt`. "
            f"Falha original: {error}"
        ) from error

    class BGEM3Embeddings(Embeddings):
        def __init__(self, model_name: str) -> None:
            use_fp16 = torch.cuda.is_available()
            self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            vectors = self.model.encode(
                texts,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )["dense_vecs"]
            return [vector.tolist() for vector in vectors]

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

    return BGEM3Embeddings(model_name)


def evaluate_rows(
    rows: list[dict[str, Any]],
    metric_names: Iterable[str] = DEFAULT_METRICS,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
):
    try:
        from datasets import Dataset
        from ragas import evaluate
    except ImportError as error:
        raise RuntimeError(
            "Instale as dependencias de avaliacao com "
            "`pip install -r requirements/evaluation.txt`. "
            f"Falha original: {error}"
        ) from error

    dataset = Dataset.from_list(
        [
            {
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row["ground_truth"],
            }
            for row in rows
        ]
    )
    return evaluate(
        dataset,
        metrics=_metric_objects(metric_names),
        llm=build_groq_judge(judge_model),
        embeddings=build_local_embeddings(embedding_model),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia o NVIDIA RAG com RAGAS.")
    parser.add_argument("--examples", required=True, type=Path, help="JSONL com question e ground_truth opcional.")
    parser.add_argument("--output", type=Path, help="Caminho para salvar linhas avaliadas em JSON.")
    parser.add_argument("--metrics", nargs="*", default=list(DEFAULT_METRICS), help="Metricas RAGAS.")
    parser.add_argument(
        "--judge-model",
        default=os.getenv("RAGAS_JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
        help="Modelo Groq usado pelo RAGAS como avaliador.",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("RAGAS_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        help="Modelo local de embeddings usado pelo RAGAS.",
    )
    args = parser.parse_args()

    rows = build_ragas_rows(load_examples(args.examples))
    result = evaluate_rows(
        rows,
        args.metrics,
        judge_model=args.judge_model,
        embedding_model=args.embedding_model,
    )
    print(result)
    if args.output:
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
