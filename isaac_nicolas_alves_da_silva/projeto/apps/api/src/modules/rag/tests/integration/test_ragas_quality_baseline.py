"""Baseline de qualidade do RAG com Ragas (Fase 2, docs/roadmap_evolucao_tecnica_mvp.md).

Mede faithfulness/answer_relevancy/context_precision/context_recall do
fluxo real ``SearchEvidence`` -> ``AnswerQuestion`` contra o conteudo
NVIDIA Knowledge V2 ja ingerido (17/20 fontes; ver
``docs/diagnostico_fraquezas_e_tecnologias_recomendadas.md``).

Chama Gemini de verdade duas vezes por pergunta (geracao da resposta RAG +
avaliacao Ragas), e e' o primeiro teste do projeto que faz isso - por
ser lento e ter custo real de API, e' opt-in via ``RUN_RAGAS_EVAL=1``,
nao roda so porque Postgres/Qdrant/GEMINI_API_KEY estao disponiveis
(diferente do resto da suite de integracao).

Numero de baseline desta rodada deve ser registrado em
``docs/roadmap_evolucao_tecnica_mvp.md`` apos a primeira execucao real -
serve de comparacao para a Fase 3 (BM25/pg_search), que so deve ser
adotada se medir uma melhora real sobre este numero.
"""

import os
import socket
import warnings
from urllib.parse import urlparse

import pytest

from apps.api.src.config.settings import get_settings
from apps.api.src.modules.rag.application.dto import AnswerQuestionInput
from apps.api.src.modules.rag.factories.rag_factory import RagFactory

RAGAS_RETRIEVAL_LIMIT = 5
RAGAS_MIN_ACCEPTABLE_SCORE = 0.75

GOLDEN_QUESTIONS: list[dict[str, str]] = [
    # nvidia-nim-docs, monai-docs e rapids-docs ficam de fora de proposito:
    # sao os 3 gaps conhecidos do NVIDIA Knowledge V2 (2 DNS + 1 estrategias
    # de scraping esgotadas) - nao tem conteudo real ingerido, perguntar
    # sobre eles testaria o caminho "sem evidencia", nao a qualidade do RAG.
    {
        "question": "What does NVIDIA NeMo do?",
        "reference": (
            "NVIDIA NeMo is a generative AI framework for creating, "
            "customizing, and deploying LLMs, multimodal, and speech "
            "models, including fine-tuning and training."
        ),
    },
    {
        "question": "What is NeMo Guardrails for?",
        "reference": (
            "NeMo Guardrails is an open-source toolkit to add programmable "
            "guardrails to LLM-based conversational agents, controlling "
            "topics, safety, and behavior."
        ),
    },
    {
        "question": "What does NVIDIA Triton Inference Server provide?",
        "reference": (
            "Triton Inference Server serves models from multiple "
            "frameworks with batching, ensembles, metrics, Kubernetes "
            "integration, and HTTP/gRPC APIs."
        ),
    },
    {
        "question": "What is TensorRT-LLM optimized for?",
        "reference": (
            "TensorRT-LLM optimizes and runs LLM inference on NVIDIA GPUs, "
            "focused on throughput, latency, and efficiency."
        ),
    },
    {
        "question": "What does NVIDIA TensorRT do?",
        "reference": (
            "TensorRT is an SDK to optimize and accelerate deep learning "
            "inference on NVIDIA GPUs, supporting PyTorch, TensorFlow, and "
            "ONNX models."
        ),
    },
    {
        "question": "What capabilities does NVIDIA Riva provide?",
        "reference": (
            "NVIDIA Riva provides speech AI capabilities including "
            "automatic speech recognition (ASR), text-to-speech (TTS), and "
            "neural translation."
        ),
    },
    {
        "question": "What is NVIDIA AI Enterprise?",
        "reference": (
            "NVIDIA AI Enterprise is an enterprise software suite to "
            "develop, deploy, and operate AI in production with support, "
            "governance, and NIM."
        ),
    },
    {
        "question": "What benefits does the NVIDIA Inception program offer startups?",
        "reference": (
            "NVIDIA Inception offers startups cloud/GPU credits, technical "
            "support, access to an investor community, and co-marketing to "
            "accelerate AI companies."
        ),
    },
    {
        "question": "What is NVIDIA Morpheus designed for?",
        "reference": (
            "NVIDIA Morpheus is an accelerated AI framework for "
            "cybersecurity, detecting threats and anomalies, analyzing "
            "logs, and responding to incidents."
        ),
    },
    {
        "question": "What is cuDF used for?",
        "reference": (
            "cuDF is a GPU-accelerated dataframe API compatible with "
            "pandas-style workloads, used to manipulate data and "
            "accelerate ETL pipelines."
        ),
    },
    {
        "question": "What is cuML used for?",
        "reference": (
            "cuML is a GPU-accelerated machine learning library with an "
            "interface similar to scikit-learn."
        ),
    },
    {
        "question": "What does NVIDIA Clara provide for healthcare and life sciences?",
        "reference": (
            "NVIDIA Clara is a platform for healthcare and life sciences, "
            "including medical imaging, genomics, and drug discovery."
        ),
    },
]


def _qdrant_is_available() -> bool:
    settings = get_settings()
    parsed = urlparse(settings.qdrant_url)
    host = parsed.hostname
    port = parsed.port or 6333
    if host is None:
        return False
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.ragas_eval,
    pytest.mark.skipif(
        os.getenv("RUN_RAGAS_EVAL") != "1",
        reason="opt-in: defina RUN_RAGAS_EVAL=1 (chama Gemini de verdade, lento e pago)",
    ),
    pytest.mark.skipif(
        not get_settings().gemini_api_key,
        reason="GEMINI_API_KEY nao configurada",
    ),
    pytest.mark.skipif(
        not _qdrant_is_available(), reason="qdrant indisponivel"
    ),
]


@pytest.mark.anyio
async def test_ragas_baseline_against_nvidia_knowledge() -> None:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

    settings = get_settings()
    answer_question = RagFactory.create_answer_question()

    rows = []
    for item in GOLDEN_QUESTIONS:
        result = await answer_question.answer(
            AnswerQuestionInput(
                query=item["question"],
                source_type="nvidia_knowledge",
                limit=RAGAS_RETRIEVAL_LIMIT,
            )
        )
        contexts = [evidence.text for evidence in result.evidences] or [""]
        rows.append(
            {
                "user_input": item["question"],
                "response": result.answer,
                "retrieved_contexts": contexts,
                "reference": item["reference"],
                "source_urls": [evidence.source_url for evidence in result.evidences],
            }
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
        )

        evaluator_llm = LangchainLLMWrapper(
            ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=0.0,
            )
        )
        evaluator_embeddings = LangchainEmbeddingsWrapper(
            GoogleGenerativeAIEmbeddings(
                model=settings.gemini_embedding_model,
                google_api_key=settings.gemini_api_key,
            )
        )

        dataset = EvaluationDataset.from_list(
            [
                {
                    key: value
                    for key, value in row.items()
                    if key != "source_urls"
                }
                for row in rows
            ]
        )
        result = evaluate(
            dataset=dataset,
            metrics=[
                Faithfulness(llm=evaluator_llm),
                AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
                ContextPrecision(llm=evaluator_llm),
                ContextRecall(llm=evaluator_llm),
            ],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        )

    frame = result.to_pandas()
    scores = frame.mean(numeric_only=True)
    print("\nRagas baseline (NVIDIA Knowledge V2):")
    print(scores)
    if os.getenv("RAGAS_PRINT_ROWS") == "1":
        diagnostics = frame[
            [
                "user_input",
                "faithfulness",
                "answer_relevancy",
                "context_precision",
                "context_recall",
            ]
        ].copy()
        diagnostics["source_urls"] = [row["source_urls"] for row in rows]
        print("\nRagas per-question diagnostics:")
        print(diagnostics.to_string(index=False))

    for metric in (
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    ):
        assert scores[metric] >= RAGAS_MIN_ACCEPTABLE_SCORE
