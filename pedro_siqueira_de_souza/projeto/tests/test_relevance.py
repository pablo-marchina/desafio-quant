"""Testes do Relevance Filter Agent — LLM falso (sem rede)."""
from agents.relevance import _Selection, relevance_node


class _FakeStructuredLLM:
    """Imita o `.invoke()` de um LLM com structured output, devolvendo um
    _Selection fixo (ou disparando erro, para testar o fallback)."""

    def __init__(self, selection=None, erro=False):
        self._selection = selection
        self._erro = erro

    def invoke(self, _prompt):
        if self._erro:
            raise RuntimeError("LLM fora do ar")
        return self._selection


class _FakeLLM:
    def __init__(self, selection=None, erro=False):
        self._selection = selection
        self._erro = erro

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self._selection, self._erro)


def _patch(monkeypatch, selection=None, erro=False):
    monkeypatch.setattr(
        "agents.relevance.get_llm", lambda: _FakeLLM(selection, erro)
    )


def _raw(*nomes):
    return [{"name": n, "source": "x", "source_url": "u"} for n in nomes]


def test_mantem_so_as_relevantes_sem_completar(monkeypatch):
    # Com folga no teto, devolve SÓ as on-topic — não completa com off-topic.
    from core.config import settings
    monkeypatch.setattr(settings, "max_startups", 10)
    _patch(monkeypatch, _Selection(selected_names=["AbacatePay", "Bamboo DCM"],
                                   reasoning="fintechs"))
    state = {"query": "startups de finanças", "search_terms": ["fintech"],
             "raw_startups": _raw("AbacatePay", "CleanCloud", "Bamboo DCM", "Squid")}
    out = relevance_node(state)

    nomes = [r["name"] for r in out["raw_startups"]]
    assert nomes == ["AbacatePay", "Bamboo DCM"]   # lavanderia e energia ficam de fora
    assert "2/4" in out["messages"][0][1]


def test_devolve_poucas_quando_poucas_relevantes(monkeypatch):
    # Poucas relevantes => lista curta (não reenche com ruído).
    from core.config import settings
    monkeypatch.setattr(settings, "max_startups", 10)
    _patch(monkeypatch, _Selection(selected_names=["Bamboo DCM"], reasoning="fintech"))
    state = {"query": "finanças", "search_terms": [],
             "raw_startups": _raw("AbacatePay", "CleanCloud", "Bamboo DCM", "Squid")}
    out = relevance_node(state)

    assert [r["name"] for r in out["raw_startups"]] == ["Bamboo DCM"]


def test_casamento_de_nome_e_case_insensitive(monkeypatch):
    _patch(monkeypatch, _Selection(selected_names=["abacatepay"], reasoning="x"))
    state = {"query": "finanças", "search_terms": [], "raw_startups": _raw("AbacatePay")}
    out = relevance_node(state)
    assert [r["name"] for r in out["raw_startups"]] == ["AbacatePay"]


def test_respeita_o_teto_max_startups(monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "max_startups", 2)
    _patch(monkeypatch, _Selection(selected_names=["A", "B", "C", "D"], reasoning="x"))
    state = {"query": "q", "search_terms": [], "raw_startups": _raw("A", "B", "C", "D")}
    out = relevance_node(state)
    assert len(out["raw_startups"]) == 2


def test_fallback_quando_llm_falha(monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "max_startups", 3)
    _patch(monkeypatch, erro=True)  # LLM dispara erro
    state = {"query": "q", "search_terms": [], "raw_startups": _raw("A", "B", "C", "D", "E")}
    out = relevance_node(state)
    # degrada para as primeiras max_startups, sem quebrar
    assert [r["name"] for r in out["raw_startups"]] == ["A", "B", "C"]
    assert "fallback" in out["messages"][0][1]


def test_nada_relevante_devolve_vazio(monkeypatch):
    # O LLM rodou e não achou nada on-topic -> lista vazia (honesto, sem ruído).
    from core.config import settings
    monkeypatch.setattr(settings, "max_startups", 2)
    _patch(monkeypatch, _Selection(selected_names=[], reasoning="nada casou"))
    state = {"query": "q", "search_terms": [], "raw_startups": _raw("A", "B", "C")}
    out = relevance_node(state)
    assert out["raw_startups"] == []


def test_entrada_vazia_passa_direto_sem_llm(monkeypatch):
    # sem raw_startups -> não deve nem chamar o LLM (se chamasse, o None quebraria)
    monkeypatch.setattr("agents.relevance.get_llm",
                        lambda: (_ for _ in ()).throw(AssertionError("não chamar LLM")))
    out = relevance_node({"query": "q", "raw_startups": []})
    assert out["raw_startups"] == []


def test_sem_query_passa_direto(monkeypatch):
    monkeypatch.setattr("agents.relevance.get_llm",
                        lambda: (_ for _ in ()).throw(AssertionError("não chamar LLM")))
    out = relevance_node({"query": "", "raw_startups": _raw("A", "B")})
    assert len(out["raw_startups"]) == 2
