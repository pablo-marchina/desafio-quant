"""Testes do nó briefing (offline — LLM monkeypatchado).

O nó encadeia redigir → revisar (reflection). Os testes mockam as duas funções e
controlam o toggle `briefing_reflection`. `numeros_sem_fonte` é determinístico (sem LLM).
"""

import pytest

from app import briefing as brf_mod
from app.state import DadosEmpresa, RadarState, Recomendacao, Score


@pytest.fixture(autouse=True)
def reflection_ligada(monkeypatch):
    """Por padrão: reflection ligada e chave LLM presente."""
    monkeypatch.setattr(brf_mod.settings, "briefing_reflection", True)
    monkeypatch.setattr(brf_mod.settings, "groq_api_key", "fake-key")


def test_briefing_aplica_reflection(monkeypatch):
    monkeypatch.setattr(brf_mod, "redigir", lambda state: "## Rascunho com 10× inventado")
    monkeypatch.setattr(brf_mod, "revisar", lambda rascunho, contexto: "## Briefing revisado")

    out = brf_mod.briefing(RadarState(consulta="Tractian"))
    assert out["briefing"] == "## Briefing revisado"  # saiu a versão revisada, não o rascunho


def test_reflection_recebe_score_e_funding_como_material(monkeypatch):
    # fix do over-strip: o revisor precisa ver score/funding como material VÁLIDO,
    # senão apaga esses números legítimos por não estarem no contexto_rag.
    capturado = {}
    monkeypatch.setattr(brf_mod, "redigir", lambda state: "## Briefing " + ("linha. " * 20))
    monkeypatch.setattr(
        brf_mod, "revisar",
        lambda rascunho, material: capturado.update(material=material) or rascunho,
    )
    state = RadarState(
        dados_estruturados=DadosEmpresa(nome="Tractian", funding="R$ 700 milhões"),
        recomendacao=Recomendacao(tecnologias=["Triton"]),
        score=Score(ai_native=9, composto=7.5),
        contexto_rag=["Triton serve modelos [fonte: https://docs.nvidia.com]"],
    )
    brf_mod.briefing(state)

    blob = " ".join(capturado["material"])
    assert "7.5" in blob    # o score composto é material permitido
    assert "700" in blob    # o funding do perfil também
    assert "docs.nvidia.com" in blob  # e o contexto NVIDIA segue lá


def test_briefing_reflection_degenerada_mantem_rascunho(monkeypatch):
    # o revisor "pediu o briefing" em vez de revisar → a desculpa NÃO pode virar o briefing
    rascunho = "## Briefing Tractian\n" + ("conteúdo relevante e sustentado. " * 20)
    monkeypatch.setattr(brf_mod, "redigir", lambda state: rascunho)
    monkeypatch.setattr(
        brf_mod, "revisar",
        lambda r, contexto: "Desculpe, não recebi o conteúdo do briefing. Poderia enviá-lo?",
    )

    out = brf_mod.briefing(RadarState(consulta="Tractian"))
    assert out["briefing"] == rascunho  # manteve o rascunho, descartou a desculpa curta


def test_briefing_sem_reflection_usa_rascunho(monkeypatch):
    monkeypatch.setattr(brf_mod.settings, "briefing_reflection", False)
    monkeypatch.setattr(brf_mod, "redigir", lambda state: "## Rascunho")

    def nao_deveria(rascunho, contexto):
        raise AssertionError("revisar não deveria ser chamado com reflection desligada")

    monkeypatch.setattr(brf_mod, "revisar", nao_deveria)

    out = brf_mod.briefing(RadarState(consulta="Tractian"))
    assert out["briefing"] == "## Rascunho"


def test_numeros_sem_fonte_sinaliza_metrica_inventada():
    contexto = ["A Tractian usa sensores IoT [fonte: https://x.com]"]
    fora = brf_mod.numeros_sem_fonte("Reduz o tempo em 10× e a latência em 50%.", contexto)
    assert "10×" in fora
    assert "50%" in fora


def test_numeros_sem_fonte_ok_quando_presente_nas_fontes():
    contexto = ["Benchmark oficial: 3x de throughput e 40% menos latência [fonte: https://docs.nvidia.com]"]
    # os mesmos números aparecem nas fontes → não são sinalizados
    assert brf_mod.numeros_sem_fonte("Ganha 3x de throughput com 40% menos latência.", contexto) == []


def test_numeros_sem_fonte_ignora_score_e_data():
    # score (6.67), data (16 Jul 2026) e funding (R$ 700 mi) não são métricas de melhoria
    contexto = ["(sem fontes numéricas)"]
    texto = "Composto 6.67. Data 16 Jul 2026. Financiamento R$ 700 milhões."
    assert brf_mod.numeros_sem_fonte(texto, contexto) == []
