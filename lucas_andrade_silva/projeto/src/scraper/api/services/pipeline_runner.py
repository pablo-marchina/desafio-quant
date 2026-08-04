from __future__ import annotations

from typing import Any

from scraper.api.services.job_manager import ProgressCallback


class PipelineRunner:
    """Thin adapters around existing callable pipeline entry points."""

    def company_registration(
        self, candidate_id: str, progress: ProgressCallback
    ) -> dict[str, Any]:
        from scraper.enrichment_pipeline.nodes.cnpj_lookup import (
            lookup_cnpj,
        )
        from scraper.enrichment_pipeline.nodes.update_supabase import (
            ensure_results_schema,
            load_candidates,
            save_enrichment_result,
        )

        progress(10)
        candidates = load_candidates(company_id=candidate_id)
        if not candidates:
            raise LookupError("Startup candidate not found")

        candidate = candidates[0]
        cnpj_data = lookup_cnpj(candidate)
        if not cnpj_data.get("cnpj"):
            raise LookupError(
                "Nenhum CNPJ compatível foi encontrado para esta startup."
            )

        progress(75)
        ensure_results_schema()
        save_enrichment_result(
            {
                "candidate": candidate,
                "cnpj_data": cnpj_data,
                "enrichment_status": (
                    candidate.get("enrichment_status") or "needs_review"
                ),
                "is_active": candidate.get("is_active", True),
                "errors": {},
            }
        )
        progress(95)
        return {"updated": True, "cnpj": cnpj_data["cnpj"]}

    def identity_check(
        self, candidate_id: str, progress: ProgressCallback
    ) -> dict[str, Any]:
        from scraper.enrichment_pipeline.main import run

        progress(10)
        result = run(
            company_id=candidate_id,
            mode="identity-only",
            no_cache=True,
        )
        progress(95)
        return result

    def enrich(
        self, candidate_id: str, progress: ProgressCallback
    ) -> dict[str, Any]:
        from scraper.enrichment_pipeline.main import run

        progress(10)
        result = run(
            company_id=candidate_id,
            mode="full",
            no_cache=True,
        )
        progress(95)
        return result
