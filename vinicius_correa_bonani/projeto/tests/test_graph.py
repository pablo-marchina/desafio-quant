"""Smoke test do fluxo completo (offline, caminho feliz).

Roda o grafo de ponta a ponta sem tocar rede nem API: busca, fetch HTTP, extração
e classificação por LLM são monkeypatchados. A evidência é suficiente (3 domínios
+ campos), então NÃO entra no loop e segue até o briefing.
"""

import pytest

from app import (
    briefing, classifier, evidence_validator, extractor, rag, recommendation, scraper, search_planner,
)
from app.graph import graph
from app.state import (
    Classificacao, DadosEmpresa, RadarState, Recomendacao, Score, VerificacaoAfirmacao,
)

HTML = "<html><body><article><p>" + ("Tractian faz IA industrial. " * 10) + "</p></article></body></html>"


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(
        search_planner, "buscar_urls",
        lambda consulta, top_n=None, queries_extra=None: ["https://a.com/x", "https://b.com/y", "https://c.com/z"],
    )
    monkeypatch.setattr(scraper, "permitido_por_robots", lambda url: True)
    monkeypatch.setattr(scraper, "fetch_url", lambda url: HTML)
    monkeypatch.setattr(
        extractor, "extract_dados",
        lambda textos, nome, fontes: DadosEmpresa(
            nome=nome, setor="Indústria", descricao="manutenção preditiva", tecnologias=["IoT"], fontes=fontes
        ),
    )
    monkeypatch.setattr(
        classifier, "classificar",
        lambda dados: Classificacao(rotulo="ai-native", justificativa="core de IA"),
    )
    # grounding do Evidence Validator: setor/descricao sustentados (sem tocar o LLM)
    monkeypatch.setattr(
        evidence_validator, "verificar_afirmacoes",
        lambda dados, conteudo: [
            VerificacaoAfirmacao(campo="setor", valor=dados.setor or "", sustentada=True, fonte="https://a.com/x"),
            VerificacaoAfirmacao(campo="descricao", valor=dados.descricao, sustentada=True, fonte="https://a.com/x"),
        ],
    )
    monkeypatch.setattr(
        rag, "recuperar",
        lambda q: [{"texto": "Triton serve modelos", "fonte": "https://docs.nvidia.com/triton"}],
    )
    monkeypatch.setattr(
        recommendation, "recomendar",
        lambda dados, classificacao, contexto_rag: Recomendacao(
            tecnologias=["Triton"], evidencias=["https://docs.nvidia.com/triton"],
        ),
    )
    monkeypatch.setattr(
        recommendation, "pontuar_em_painel",
        lambda dados, classificacao, contexto_rag: Score(ai_native=8, nvidia_fit=9, tracao=6, time_ia=7),
    )
    monkeypatch.setattr(briefing, "redigir", lambda state: "## Briefing (fake)")
    monkeypatch.setattr(briefing, "revisar", lambda rascunho, contexto: rascunho)


def test_pipeline_preenche_todos_os_campos(offline):
    final = graph.invoke(RadarState(consulta="Tractian"))

    assert final["alvos"] == ["Tractian"]
    assert final["urls_busca"]
    assert final["conteudo_bruto"]
    assert final["dados_estruturados"].nome == "Tractian"
    assert final["classificacao"] == "ai-native"
    assert final["classificacao_detalhe"].rotulo == "ai-native"
    assert final["evidencias_ok"] is True
    assert final["tentativas"] == 1          # sem loop (evidência suficiente de 1ª)
    assert final["contexto_rag"]
    assert final["recomendacao"] is not None
    assert final["recomendacao"].tecnologias
    assert final["score"].composto > 0
    assert final["briefing"]
