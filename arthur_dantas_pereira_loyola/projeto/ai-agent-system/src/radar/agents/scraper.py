from __future__ import annotations

from radar.graph.progress import get_tracker
from radar.graph.state import RadarState
from radar.schemas import PipelineError, SourceDocument
from radar.scraping.collectors import WebCollector
from radar.scraping.provider_factory import build_web_collector


def collect_sources(state: RadarState) -> list[SourceDocument]:
    plan = state["search_plan"]
    collector = build_web_collector()
    return collector.collect(plan)


def collect_sources_with_errors(
    state: RadarState,
    collector: WebCollector | None = None,
) -> tuple[list[SourceDocument], list[PipelineError]]:
    plan = state["search_plan"]
    active_collector = collector or build_web_collector()

    tracker = get_tracker()
    if tracker:
        tracker.set_detail(
            "scraper",
            f"Buscando com {active_collector.__class__.__name__}..."
        )

    detailed_collect = getattr(active_collector, "collect_with_errors", None)
    if callable(detailed_collect):
        import traceback as _tb
        try:
            sources, errors = detailed_collect(plan)
        except Exception:
            with open(r"C:\Users\Inteli\AppData\Local\Temp\opencode\scraper_error.txt", "w") as _f:
                _tb.print_exc(file=_f)
            raise
        if tracker:
            if errors:
                tracker.set_detail(
                    "scraper",
                    f"Coletadas {len(sources)} fontes, {len(errors)} erros"
                )
            else:
                tracker.set_detail(
                    "scraper",
                    f"Coletadas {len(sources)} fontes com sucesso"
                )
        return sources, errors

    try:
        sources = active_collector.collect(plan)
        if tracker:
            tracker.set_detail(
                "scraper",
                f"Coletadas {len(sources)} fontes com sucesso"
            )
        return sources, []
    except Exception as exc:
        if tracker:
            tracker.set_detail("scraper", f"Erro na coleta: {str(exc)[:100]}")
        return [], [
            PipelineError(
                step="scraper.collect",
                message=str(exc),
                recoverable=True,
                provider=active_collector.__class__.__name__,
                error_type=type(exc).__name__,
            )
        ]
