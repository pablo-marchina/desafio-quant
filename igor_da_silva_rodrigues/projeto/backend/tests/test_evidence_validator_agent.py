import json

import requests

from app.agents.evidence_validator_agent import (
    salvar_validacao_evidencias,
    validar_evidencias_scraper,
)


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def get(self, url, **kwargs):
        if "quebrada" in url:
            return FakeResponse(404)
        return FakeResponse(200)


def _payload():
    return {
        "startup": "Clara Pagamentos",
        "resultados_buscas": [
            {
                "titulo": "Clara Pagamentos apresenta analista financeiro com IA",
                "url": "https://exame.com/negocios/clara-ia",
                "snippet": "A Clara Pagamentos usa inteligencia artificial e machine learning em seu produto financeiro.",
            },
            {
                "titulo": "Clara Pagamentos em evento",
                "url": "https://eventos.example.com/agenda",
                "snippet": "Clara Pagamentos participara do evento anual.",
            },
            {
                "titulo": "Outra Clara",
                "url": "https://example.com/homonimo",
                "snippet": "Clara e o nome de uma artista brasileira.",
            },
            {
                "titulo": "Clara Pagamentos",
                "url": "https://example.com/quebrada",
                "snippet": "Clara Pagamentos usa IA.",
            },
        ],
        "paginas_completas": [
            {
                "url": "https://clara.com.br/blog/analista-ia",
                "titulo_pagina": "Tecnologia da Clara Pagamentos",
                "conteudo_markdown": (
                    "A Clara Pagamentos desenvolveu sua plataforma e utiliza machine learning "
                    "para automatizar a analise de gastos. A tecnologia da Clara Pagamentos "
                    "apoia o produto financeiro com modelos preditivos e automacao inteligente."
                ),
                "metadados": {},
            }
        ],
    }


def test_validator_classifies_sources_and_discards_noise():
    result = validar_evidencias_scraper(
        _payload(),
        site_oficial="https://clara.com.br",
        session=FakeSession(),
    )

    official = next(item for item in result["evidencias_validadas"] if item["tipo_fonte"] == "oficial")
    press = next(item for item in result["evidencias_validadas"] if item["tipo_fonte"] == "imprensa")

    assert official["declaracao_propria"] is True
    assert official["credibilidade_fonte"] == 0.7
    assert press["credibilidade_fonte"] == 0.9
    assert press["contem_evidencia_ia"] is True
    assert any(item["motivo"].startswith("homonimo_potencial") for item in result["evidencias_descartadas"])
    assert any(item["motivo"] == "url_quebrada" for item in result["evidencias_descartadas"])
    assert result["erros_validacao"]


def test_validator_marks_technology_as_corroborated_across_independent_domains():
    result = validar_evidencias_scraper(
        _payload(),
        site_oficial="https://clara.com.br",
        session=FakeSession(),
    )

    machine_learning = [
        item
        for item in result["evidencias_validadas"]
        if "machine learning" in item["tecnologias_detectadas"]
    ]

    assert len(machine_learning) == 2
    assert all(item["corroborada"] for item in machine_learning)
    assert result["resumo_consolidado"]["fontes_corroboradas"] == 2
    assert "machine learning" in result["resumo_consolidado"]["tecnologias_detectadas"]
    assert result["resumo_consolidado"]["afirmacoes_chave"]


def test_validator_accepts_prompt_nested_input_contract():
    nested = {
        "startup": "Clara Pagamentos",
        "dados_brutos": {
            "resultados_busca": [
                {
                    "consulta": "Clara IA",
                    "resultados": [
                        {
                            "titulo": "Clara Pagamentos usa IA",
                            "url": "https://neofeed.com.br/clara",
                            "snippet": "A plataforma Clara Pagamentos utiliza inteligencia artificial no produto.",
                        }
                    ],
                }
            ],
            "paginas_coletadas": [],
            "varredura_complementar": [],
        },
    }

    result = validar_evidencias_scraper(nested, session=FakeSession())

    assert result["evidencias_validadas"][0]["tipo_fonte"] == "imprensa"


def test_validator_saves_traceable_json(tmp_path):
    result = validar_evidencias_scraper(
        _payload(),
        site_oficial="https://clara.com.br",
        session=FakeSession(),
    )

    path = salvar_validacao_evidencias(result, tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["startup"] == "Clara Pagamentos"
    assert path.name == "evidencias_validadas_clara-pagamentos.json"
