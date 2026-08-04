from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from app.agents.ai_maturity_classifier_agent import (
    classificar_maturidade_ia,
    salvar_classificacao_maturidade,
)
from app.agents.evidence_validator_agent import (
    salvar_validacao_evidencias,
    validar_evidencias_scraper,
)
from app.agents.scraper_agent import executar_scraper_agent, salvar_resultado_scraper
from app.agents.search_planner_agent import planejar_busca_ia_startup


def executar_pipeline_investigacao_ia(
    startup: dict[str, Any],
    contexto: str | None = None,
    session: requests.Session | None = None,
    delay_seconds: float = 2.0,
    respect_robots: bool = True,
    salvar_resultado: bool = True,
    output_dir: Path | None = None,
    validation_output_dir: Path | None = None,
    classification_output_dir: Path | None = None,
    verificar_urls: bool = True,
) -> dict[str, Any]:
    plano = planejar_busca_ia_startup(startup, contexto=contexto)
    coleta = executar_scraper_agent(
        plano,
        session=session,
        delay_seconds=delay_seconds,
        respect_robots=respect_robots,
    )
    validacao = validar_evidencias_scraper(
        coleta,
        site_oficial=plano.get("site_oficial"),
        session=session,
        verificar_urls=verificar_urls,
    )
    classificacao = classificar_maturidade_ia(validacao)

    output_path = None
    validation_output_path = None
    classification_output_path = None
    if salvar_resultado:
        output_path = salvar_resultado_scraper(coleta, output_dir=output_dir)
        validation_output_path = salvar_validacao_evidencias(
            validacao,
            output_dir=validation_output_dir,
        )
        classification_output_path = salvar_classificacao_maturidade(
            classificacao,
            output_dir=classification_output_dir,
        )

    return {
        "startup": plano["startup"],
        "status": coleta["status"],
        "plano": plano,
        "coleta": coleta,
        "validacao": validacao,
        "classificacao_ia": classificacao,
        "arquivo_saida": str(output_path) if output_path else None,
        "arquivo_validacao": str(validation_output_path) if validation_output_path else None,
        "arquivo_classificacao": str(classification_output_path) if classification_output_path else None,
    }
