"""Teste da avaliação de RAG (função pura `acertou`, sem tocar o Qdrant)."""

from app.eval_rag import acertou


def test_acertou_quando_tech_aparece():
    passagens = [
        {"titulo": "NVIDIA Clara / MONAI", "texto": "Medical Open Network for AI"},
        {"titulo": "Triton", "texto": "serving"},
    ]
    assert acertou(["Clara", "MONAI"], passagens) is True
    assert acertou(["Riva"], passagens) is False


def test_acertou_olha_titulo_e_texto():
    passagens = [{"titulo": "doc", "texto": "TensorRT-LLM otimiza inferência"}]
    assert acertou(["TensorRT-LLM"], passagens) is True
