from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.persistence.batch_repository import BatchRepository
from app.persistence.persistence_service import PipelinePersistence
from app.processing.cubo_curated_builder import construir_curated_cubo_de_payload
from app.processing.cubo_data_lapidator import lapidar_dados_cubo
from app.scraping.cubo_portfolio_scraper import (
    StartupCubo,
    coletar_startups_cubo_com_erros,
)


Collector = Callable[..., tuple[list[StartupCubo], list[dict[str, Any]]]]


class StartupDiscoveryService:
    """Collect, curate and idempotently import startups from the Cubo portfolio."""

    def __init__(
        self,
        persistence: PipelinePersistence,
        collector: Collector = coletar_startups_cubo_com_erros,
        batch_repository: BatchRepository | None = None,
    ) -> None:
        self.persistence = persistence
        self.collector = collector
        self.batch_repository = batch_repository or BatchRepository(persistence)

    def discover(self, limit: int, offset: int = 0) -> dict[str, Any]:
        collected, errors = self.collector(limit=limit, offset=offset)
        raw_payload = {
            "status": "sucesso" if collected and not errors else "parcial",
            "startups": [startup.to_dict() for startup in collected],
            "erros": errors,
        }
        processed = lapidar_dados_cubo(raw_payload)["JSON_LAPIDADO"]
        curated = construir_curated_cubo_de_payload(processed)

        created = 0
        existing = 0
        startup_ids: list[str] = []
        new_companies: list[dict[str, Any]] = []
        for company in curated["startups"]:
            startup_id, was_created = self.persistence.save_startup_with_status(
                _persistence_payload(company)
            )
            startup_ids.append(str(startup_id))
            created += int(was_created)
            existing += int(not was_created)
            if was_created:
                new_companies.append(company)

        batch_id = None
        if new_companies:
            batch_id = self.batch_repository.create_batch(
                source_path=f"discovery:cubo:{offset}",
                startups=new_companies,
                options={
                    "limit": len(new_companies),
                    "include_ineligible": True,
                    "max_attempts": 2,
                    "stop_on_error": False,
                    "source": "startup_discovery",
                },
            )

        return {
            "status": "success" if collected and not errors else "partial",
            "source": "Cubo Itau - Vitrine de Startups",
            "requested_limit": limit,
            "source_offset": offset,
            "collected_count": len(collected),
            "curated_count": len(curated["startups"]),
            "created_count": created,
            "existing_count": existing,
            "startup_ids": startup_ids,
            "batch_id": str(batch_id) if batch_id else None,
            "analysis_queued_count": len(new_companies),
            "errors": errors,
        }


def _persistence_payload(company: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_id": company["startup_id"],
        "nome": company["nome"],
        "site_oficial": company.get("site"),
        "categoria": company.get("categoria"),
        "cidade": company.get("cidade"),
        "estado": company.get("estado"),
        "pais": company.get("pais") or "Brasil",
        "metadata": {
            "aliases": company.get("aliases") or [],
            "descricao_curta": company.get("descricao_curta"),
            "logo_url": company.get("logo_url"),
            "qualidade": company.get("qualidade") or {},
            "fontes": company.get("fontes") or [],
            "origem": "cubo_portfolio",
        },
    }
