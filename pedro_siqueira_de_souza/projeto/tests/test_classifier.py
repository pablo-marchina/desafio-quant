"""Testes do Classifier Agent — offline, com LLM falso.

Espelha o padrão do extractor: um FakeLLM cujo `with_structured_output`
devolve sempre um `_ClassificationResult` fixo. Monkeypatch em
`agents.classifier.get_llm`. Sem rede, sem chave de API.
"""
import pytest

from agents.classifier import _ClassificationResult, classifier_node


class _FakeStructuredLLM:
    def __init__(self, result: _ClassificationResult):
        self._result = result

    def invoke(self, prompt):
        return self._result


class _FakeLLM:
    def __init__(self, result: _ClassificationResult):
        self._result = result

    def with_structured_output(self, schema):
        return _FakeStructuredLLM(self._result)


@pytest.fixture
def fixed_result() -> _ClassificationResult:
    return _ClassificationResult(
        label="AI-native",
        rationale="modelos próprios de ML são o núcleo do produto",
        confidence="high",
    )


@pytest.fixture
def patch_classifier_llm(monkeypatch, fixed_result: _ClassificationResult):
    monkeypatch.setattr("agents.classifier.get_llm", lambda: _FakeLLM(fixed_result))
    return fixed_result


def _startup(**over) -> dict:
    """StructuredStartup serializado, com extraction_basis=content por padrão."""
    base = {
        "name": "Salvy",
        "description": "Telefonia móvel para empresas.",
        "sector": "telecom",
        "stage": None,
        "funding": None,
        "tech_stack": ["Python"],
        "ai_signals": ["roteamento com ML próprio"],
        "extraction_basis": "content",
    }
    base.update(over)
    return base


def test_classifier_rotula_startup_com_conteudo(patch_classifier_llm, fixed_result):
    out = classifier_node({"extracted_startups": [_startup()]})
    c = out["classified_startups"][0]

    assert c["label"] == fixed_result.label
    assert c["rationale"] == fixed_result.rationale
    assert c["confidence"] == fixed_result.confidence
    # o StructuredStartup que entrou fica aninhado, intacto
    assert c["startup"]["name"] == "Salvy"
    assert c["startup"]["ai_signals"] == ["roteamento com ML próprio"]
    assert len(out["messages"]) == 1
    assert "1 AI-native" in out["messages"][0][1]


def test_classifier_metadata_nao_chama_llm(monkeypatch):
    # Se o nó tocar o LLM no caminho metadata, o teste falha.
    def boom():
        raise AssertionError("LLM não deveria ser chamado para metadata")

    monkeypatch.setattr("agents.classifier.get_llm", boom)
    out = classifier_node({"extracted_startups": [
        _startup(name="Aegro", extraction_basis="metadata", ai_signals=[]),
    ]})
    c = out["classified_startups"][0]

    # sem conteúdo -> "Indeterminado", NÃO Non-AI (não conseguimos julgar)
    assert c["label"] == "Indeterminado"
    assert c["confidence"] == "low"
    assert "provisória" in c["rationale"]


def test_classifier_isola_falha_por_startup(monkeypatch):
    """Uma classificação que estoura vira fallback Non-AI/low; as demais seguem."""
    class _BoomStructured:
        def invoke(self, prompt):
            raise RuntimeError("LLM caiu")

    class _BoomLLM:
        def with_structured_output(self, schema):
            return _BoomStructured()

    monkeypatch.setattr("agents.classifier.get_llm", lambda: _BoomLLM())
    out = classifier_node({"extracted_startups": [
        _startup(name="A"),                               # vai pro LLM (e falha)
        _startup(name="B", extraction_basis="metadata"),  # metadata, sem LLM
    ]})
    classificadas = out["classified_startups"]

    assert len(classificadas) == 2  # nenhuma startup foi perdida
    assert classificadas[0]["startup"]["name"] == "A"
    assert classificadas[0]["label"] == "Indeterminado"  # LLM caiu -> não julgou
    assert classificadas[0]["confidence"] == "low"
    assert classificadas[1]["startup"]["name"] == "B"
    assert classificadas[1]["label"] == "Indeterminado"  # metadata -> não julgou


def test_classifier_nao_muta_estado_original(patch_classifier_llm):
    original = _startup()
    classifier_node({"extracted_startups": [original]})

    # o dict original do estado não foi alterado
    assert original["extraction_basis"] == "content"
    assert "label" not in original
