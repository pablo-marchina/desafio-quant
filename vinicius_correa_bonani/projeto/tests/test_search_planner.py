"""Testes do Search Planner (offline — DDGS monkeypatchado)."""

from app import search_planner as sp
from app.state import DadosEmpresa, RadarState, VerificacaoAfirmacao


class FakeDDGS:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def text(self, query, max_results=None, **kwargs):  # aceita backend=...
        return [
            {"href": "https://linkedin.com/company/tractian"},  # bloqueado
            {"href": "https://example.com/sobre"},              # normal
            {"href": "https://braziljournal.com/tractian"},     # confiável
            {"href": "https://exemplo.com/ficha.pdf"},          # pdf -> descartado
        ]


def test_buscar_urls_filtra_e_prioriza(monkeypatch):
    monkeypatch.setattr(sp, "DDGS", FakeDDGS)
    urls = sp.buscar_urls("Tractian", top_n=8)

    # LinkedIn e PDF foram descartados
    assert not any("linkedin.com" in u for u in urls)
    assert not any(u.endswith(".pdf") for u in urls)
    # domínio confiável vem antes do normal
    assert urls[0] == "https://braziljournal.com/tractian"
    assert "https://example.com/sobre" in urls


def test_campos_em_falta_detecta_vazios_e_nao_sustentados():
    # setor/descricao presentes; funding/founders/clientes/tecnologias vazios.
    # setor marcado como NÃO sustentado pelo grounding → também é gap.
    dados = DadosEmpresa(nome="X", setor="Indústria", descricao="faz X")
    state = RadarState(
        dados_estruturados=dados,
        afirmacoes_verificadas=[VerificacaoAfirmacao(campo="setor", sustentada=False)],
    )
    faltando = sp.campos_em_falta(state)

    assert "funding" in faltando        # vazio
    assert "setor" in faltando          # presente, mas não sustentado
    assert "descricao" not in faltando  # presente e sem veredito negativo


def test_campos_em_falta_vazio_na_primeira_passada():
    # sem dados ainda (1ª passada) → nada a perseguir
    assert sp.campos_em_falta(RadarState()) == []


def test_search_planner_dirige_ao_gap_no_retry(monkeypatch):
    capturado = {}

    def fake_buscar(consulta, top_n=None, queries_extra=None):
        capturado["queries_extra"] = queries_extra
        return ["https://x.com/y"]

    monkeypatch.setattr(sp, "buscar_urls", fake_buscar)
    dados = DadosEmpresa(nome="Tractian", setor="Indústria", descricao="faz X")  # funding vazio
    sp.search_planner(RadarState(consulta="Tractian", tentativas=1, dados_estruturados=dados))

    qs = capturado["queries_extra"]
    assert qs  # há queries dirigidas no retry
    assert any("investimento" in q for q in qs)  # persegue o funding faltante


def test_search_planner_primeira_passada_sem_gap(monkeypatch):
    capturado = {}

    def fake_buscar(consulta, top_n=None, queries_extra=None):
        capturado["queries_extra"] = queries_extra
        return []

    monkeypatch.setattr(sp, "buscar_urls", fake_buscar)
    sp.search_planner(RadarState(consulta="Tractian", tentativas=0))

    assert not capturado["queries_extra"]  # 1ª passada é genérica
