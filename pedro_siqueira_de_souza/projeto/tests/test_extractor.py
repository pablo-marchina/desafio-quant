"""Testes do Extractor Agent — offline, com LLM falso.

Espelha o padrão do search_planner: um FakeLLM cujo `with_structured_output`
devolve sempre um `_ExtractedFields` fixo. Monkeypatch em
`agents.extractor.get_llm`. Sem rede, sem chave de API.
"""
import pytest

from agents.extractor import _ExtractedFields, extractor_node


class _FakeStructuredLLM:
    """Imita `.invoke()` de um LLM com saída estruturada: devolve o fixo."""

    def __init__(self, fields: _ExtractedFields):
        self._fields = fields

    def invoke(self, prompt):
        return self._fields


class _FakeLLM:
    """Imita a interface mínima de um BaseChatModel."""

    def __init__(self, fields: _ExtractedFields):
        self._fields = fields

    def with_structured_output(self, schema):
        return _FakeStructuredLLM(self._fields)


@pytest.fixture
def fixed_fields() -> _ExtractedFields:
    return _ExtractedFields(
        description="Plataforma de telefonia móvel para empresas.",
        sector="telecom",
        stage="seed",
        funding="R$ 20 mi em série A",
        tech_stack=["Python", "AWS"],
        ai_signals=["roteamento de chamadas com modelos de ML próprios"],
    )


@pytest.fixture
def patch_extractor_llm(monkeypatch, fixed_fields: _ExtractedFields) -> _ExtractedFields:
    """Troca `agents.extractor.get_llm` pelo FakeLLM durante o teste."""
    monkeypatch.setattr("agents.extractor.get_llm", lambda: _FakeLLM(fixed_fields))
    return fixed_fields


def test_extractor_estrutura_startup_com_conteudo(patch_extractor_llm, fixed_fields):
    state = {"raw_startups": [
        {"name": "Salvy", "source": "latitud.com",
         "source_url": "https://www.latitud.com/portfolio",
         "content": "Salvy é telefonia móvel para empresas, com ML próprio."},
    ]}
    out = extractor_node(state)
    salvy = out["extracted_startups"][0]

    # name vem do RawStartup (não do LLM); os demais campos, do LLM falso
    assert salvy["name"] == "Salvy"
    assert salvy["description"] == fixed_fields.description
    assert salvy["ai_signals"] == fixed_fields.ai_signals
    assert salvy["extraction_basis"] == "content"
    assert len(out["messages"]) == 1
    assert "1 via conteúdo" in out["messages"][0][1]


def test_extractor_sem_conteudo_nao_chama_llm(monkeypatch):
    # Se o nó tocar o LLM nesse caminho, o teste falha — garante o "pular LLM".
    def boom():
        raise AssertionError("LLM não deveria ser chamado sem conteúdo")

    monkeypatch.setattr("agents.extractor.get_llm", boom)
    state = {"raw_startups": [
        {"name": "Aegro", "source": "wow.ac",
         "source_url": "https://www.wow.ac/portfolio", "sector": "agtech"},
    ]}
    out = extractor_node(state)
    aegro = out["extracted_startups"][0]

    assert aegro["extraction_basis"] == "metadata"
    assert aegro["ai_signals"] == []        # nada inventado
    assert aegro["description"] is None
    assert aegro["sector"] == "agtech"      # mantém a dica que a fonte trouxe


def test_extractor_isola_falha_por_startup(monkeypatch):
    """Uma extração que estoura vira fallback metadata e não derruba as demais."""
    class _BoomStructured:
        def invoke(self, prompt):
            raise RuntimeError("LLM caiu")

    class _BoomLLM:
        def with_structured_output(self, schema):
            return _BoomStructured()

    monkeypatch.setattr("agents.extractor.get_llm", lambda: _BoomLLM())
    state = {"raw_startups": [
        {"name": "A", "source": "x", "source_url": "u", "content": "tem conteúdo"},
        {"name": "B", "source": "x", "source_url": "u"},  # sem conteúdo
    ]}
    out = extractor_node(state)
    estruturadas = out["extracted_startups"]

    assert len(estruturadas) == 2  # nenhuma startup foi perdida
    # a que falhou caiu pro fallback metadata
    assert estruturadas[0]["name"] == "A"
    assert estruturadas[0]["extraction_basis"] == "metadata"
    assert estruturadas[1]["name"] == "B"


def test_extractor_nao_muta_estado_original(patch_extractor_llm):
    original = {"name": "Salvy", "source": "latitud.com",
                "source_url": "u", "content": "conteúdo"}
    extractor_node({"raw_startups": [original]})

    # o dict original do estado não ganhou chaves novas
    assert set(original.keys()) == {"name", "source", "source_url", "content"}
