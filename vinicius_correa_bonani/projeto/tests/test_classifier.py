"""Testes do Classifier (offline — LLM monkeypatchado)."""

from app import classifier as clf
from app.state import Classificacao, DadosEmpresa, RadarState


def test_classifier_preenche_rotulo_e_detalhe(monkeypatch):
    fake = Classificacao(
        rotulo="ai-native",
        eixo_produto="IA é o core",
        eixo_dados_modelo="modelo próprio",
        eixo_stack="infra própria",
        justificativa="3 eixos atendidos",
    )
    monkeypatch.setattr(clf, "classificar", lambda dados: fake)

    state = RadarState(dados_estruturados=DadosEmpresa(nome="Tractian", setor="Indústria"))
    out = clf.classifier(state)

    assert out["classificacao"] == "ai-native"
    assert out["classificacao_detalhe"].rotulo == "ai-native"
    assert out["classificacao_detalhe"].justificativa


def test_classifier_sem_dados_nao_chama_llm(monkeypatch):
    def nao_deveria(dados):
        raise AssertionError("não deveria classificar sem dados coletados")

    monkeypatch.setattr(clf, "classificar", nao_deveria)
    # dados vazios (busca/scraping não trouxe nada) → rótulo honesto "sem-dados"
    out = clf.classifier(RadarState(dados_estruturados=DadosEmpresa(nome="X")))
    assert out["classificacao"] == "sem-dados"


def test_self_consistency_vence_a_maioria(monkeypatch):
    # 3 votos: ai-native, ai-enabled, ai-native → maioria ai-native (2 de 3)
    votos = iter([
        Classificacao(rotulo="ai-native", justificativa="v1"),
        Classificacao(rotulo="ai-enabled", justificativa="v2"),
        Classificacao(rotulo="ai-native", justificativa="v3"),
    ])
    monkeypatch.setattr(clf, "classificar", lambda dados: next(votos))

    c = clf.classificar_consistente(DadosEmpresa(nome="Tractian"), n=3)
    assert c.rotulo == "ai-native"           # o rótulo majoritário venceu
    assert c.justificativa in ("v1", "v3")   # detalhe vem de um voto vencedor (rastreável)


def test_classifier_usa_voto_majoritario(monkeypatch):
    # o nó inteiro deve refletir a maioria, não o primeiro voto
    monkeypatch.setattr(clf.settings, "classifier_n_votos", 3)  # independe do .env
    votos = iter([
        Classificacao(rotulo="ai-enabled", justificativa="a"),
        Classificacao(rotulo="ai-native", justificativa="b"),
        Classificacao(rotulo="ai-native", justificativa="c"),
    ])
    monkeypatch.setattr(clf, "classificar", lambda dados: next(votos))

    out = clf.classifier(RadarState(dados_estruturados=DadosEmpresa(nome="X", setor="Indústria")))
    assert out["classificacao"] == "ai-native"
