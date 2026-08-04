"""Testes do nó recommendation (offline — LLM monkeypatchado)."""

from app import recommendation as rec_mod
from app.state import DadosEmpresa, RadarState, Recomendacao, Score


def test_recommendation_monta_rec_e_score(monkeypatch):
    fake_rec = Recomendacao(tecnologias=["Triton", "TensorRT-LLM"], evidencias=["https://docs.nvidia.com/triton"])
    fake_notas = Score(ai_native=10, nvidia_fit=10, tracao=10, time_ia=10)
    # agora são duas tarefas separadas: recomendar (7 campos) e pontuar (painel → notas)
    monkeypatch.setattr(rec_mod, "recomendar", lambda dados, classificacao, contexto_rag: fake_rec)
    monkeypatch.setattr(rec_mod, "pontuar_em_painel", lambda dados, classificacao, contexto_rag: fake_notas)

    state = RadarState(
        dados_estruturados=DadosEmpresa(nome="Tractian"),
        contexto_rag=["Triton serve modelos [fonte: https://docs.nvidia.com/triton]"],
    )
    out = rec_mod.recommendation(state)

    assert out["recomendacao"].tecnologias == ["Triton", "TensorRT-LLM"]
    assert out["recomendacao"].evidencias  # rastreabilidade
    assert out["score"].composto == 10.0   # todas 10, pesos somam 1.0
    assert out["score"].nvidia_fit == 10


def test_painel_de_juizes_faz_media_das_notas(monkeypatch):
    # 3 juízes com notas diferentes → o painel devolve a média de cada eixo
    votos = iter([
        Score(ai_native=6, nvidia_fit=4, tracao=2, time_ia=0),
        Score(ai_native=8, nvidia_fit=6, tracao=4, time_ia=2),
        Score(ai_native=10, nvidia_fit=8, tracao=6, time_ia=4),
    ])
    monkeypatch.setattr(rec_mod, "pontuar", lambda dados, classificacao, contexto_rag: next(votos))

    s = rec_mod.pontuar_em_painel(DadosEmpresa(nome="X"), None, [], n=3)
    assert s.ai_native == 8.0    # média de 6, 8, 10
    assert s.nvidia_fit == 6.0
    assert s.tracao == 4.0
    assert s.time_ia == 2.0
