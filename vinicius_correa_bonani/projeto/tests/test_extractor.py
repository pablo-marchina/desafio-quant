"""Testes do Extractor (offline — LLM monkeypatchado).

O extractor não grava mais no banco (persistência foi para o fim do pipeline,
via db.salvar_resultado). Só extrai e devolve dados_estruturados.
"""

from app import extractor
from app.state import DadosEmpresa, RadarState


def test_extractor_preenche_dados(monkeypatch):
    fake = DadosEmpresa(nome="Tractian", setor="Indústria", tecnologias=["IoT", "ML"])
    monkeypatch.setattr(extractor, "extract_dados", lambda textos, nome, fontes: fake)

    state = RadarState(
        alvos=["Tractian"],
        conteudo_bruto=[{"texto": "trecho", "fonte": "https://x.com"}],
    )
    out = extractor.extractor(state)

    assert out["dados_estruturados"].nome == "Tractian"
    assert out["dados_estruturados"].tecnologias == ["IoT", "ML"]


def test_extractor_sem_conteudo_nao_chama_llm(monkeypatch):
    def nao_deveria(*a, **k):
        raise AssertionError("extract_dados não deveria ser chamado sem conteúdo")

    monkeypatch.setattr(extractor, "extract_dados", nao_deveria)

    out = extractor.extractor(RadarState(alvos=["Tractian"], conteudo_bruto=[]))
    assert out["dados_estruturados"].nome == "Tractian"
