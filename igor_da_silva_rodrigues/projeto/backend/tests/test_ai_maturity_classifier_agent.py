import json

from app.agents.ai_maturity_classifier_agent import (
    classificar_maturidade_ia,
    salvar_classificacao_maturidade,
)


def _evidence(
    text,
    url="https://example.com/evidencia",
    score=0.85,
    technologies=None,
    corroborated=False,
):
    return {
        "url": url,
        "dominio": url.split("/")[2],
        "score_confianca": score,
        "contem_evidencia_ia": True,
        "trecho_evidencia": text,
        "tecnologias_detectadas": technologies or [],
        "corroborada": corroborated,
    }


def _validation(high=None, medium=None):
    return {
        "startup": "Startup Teste",
        "evidencias_validadas": high or [],
        "evidencias_medias": medium or [],
        "resumo_consolidado": {
            "nota_geral_qualidade_evidencias": 0.8,
            "fontes_corroboradas": 0,
        },
    }


def test_classifier_returns_non_ai_without_qualified_ai_evidence():
    result = classificar_maturidade_ia(_validation())

    assert result["classificacao"] == "Non-AI"
    assert result["nivel_maturidade"] == 0
    assert result["tecnologias_utilizadas"]["frameworks"] == []
    assert result["evidencias_suporte"] == []


def test_classifier_identifies_api_consumer_conservatively():
    evidence = _evidence(
        "A Startup Teste integra a OpenAI API em seu produto para oferecer um assistente virtual.",
        technologies=["gpt"],
    )

    result = classificar_maturidade_ia(_validation(high=[evidence]))

    assert result["classificacao"] == "API-consumer"
    assert result["nivel_maturidade"] == 2
    assert "OpenAI API" in result["tecnologias_utilizadas"]["modelos_apis"]
    assert any("vendor lock-in" in item for item in result["necessidades_limitacoes"])


def test_classifier_keeps_api_consumer_when_evidence_also_uses_generic_ai_terms():
    evidence = _evidence(
        "A Startup Teste usa inteligencia artificial por meio da OpenAI API.",
        technologies=["inteligencia artificial", "gpt"],
    )

    result = classificar_maturidade_ia(_validation(high=[evidence]))

    assert result["classificacao"] == "API-consumer"


def test_classifier_identifies_ai_native_and_optimized_level_five():
    evidence = _evidence(
        "A equipe de ML treina um modelo proprietario com PyTorch em GPU NVIDIA e usa TensorRT para baixa latencia.",
        technologies=["pytorch", "gpu", "nvidia", "tensorrt"],
        corroborated=True,
    )

    result = classificar_maturidade_ia(_validation(high=[evidence]))

    assert result["classificacao"] == "AI-native"
    assert result["nivel_maturidade"] == 5
    assert result["confianca_classificacao"] == 0.93
    assert result["tecnologias_utilizadas"]["frameworks"] == ["PyTorch"]
    assert "TensorRT" in result["tecnologias_utilizadas"]["infraestrutura"]


def test_classifier_identifies_ai_enabled_without_internal_development_proof():
    evidence = _evidence(
        "A plataforma da Startup Teste utiliza machine learning para automatizar a analise financeira.",
        technologies=["machine learning"],
    )

    result = classificar_maturidade_ia(_validation(high=[evidence]))

    assert result["classificacao"] == "AI-enabled"
    assert result["nivel_maturidade"] == 3
    assert result["confianca_classificacao"] == 0.77
    assert "sem comprovação suficiente" in result["justificativa"]


def test_classifier_only_uses_evidence_with_minimum_score():
    weak = _evidence("Usamos PyTorch.", score=0.3, technologies=["pytorch"])

    result = classificar_maturidade_ia(_validation(medium=[weak]))

    assert result["classificacao"] == "Non-AI"


def test_classifier_requires_attributable_proof_for_ai_native():
    evidence = _evidence(
        "Uma pagina de terceiros menciona modelo proprietario e PyTorch.",
        score=0.9,
        technologies=["pytorch"],
        corroborated=False,
    )

    result = classificar_maturidade_ia(_validation(high=[evidence]))

    assert result["classificacao"] == "AI-enabled"
    assert result["nivel_maturidade"] in {2, 3}


def test_classifier_preserves_exact_supporting_excerpt_and_saves_json(tmp_path):
    excerpt = "A Startup Teste utiliza machine learning em seu produto."
    evidence = _evidence(excerpt)
    result = classificar_maturidade_ia(_validation(high=[evidence]))

    path = salvar_classificacao_maturidade(result, tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert result["evidencias_suporte"] == [f"https://example.com/evidencia: {excerpt}"]
    assert saved["startup"] == "Startup Teste"
    assert path.name == "maturidade_ia_startup-teste.json"
