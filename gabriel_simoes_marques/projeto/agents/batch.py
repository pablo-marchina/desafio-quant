"""
Batch agent: analisa N startups em paralelo com concurrency limitada.
Semaphore(2) evita rate limit no Groq/OpenRouter.
"""

import asyncio
from dataclasses import dataclass
from models.briefing import BriefingReport
from models.score import StartupScore
from graph.pipeline import build_pipeline
from agents.scorer import score_startup
from config.llm import DEFAULT_MODEL


@dataclass
class BatchResult:
    startup_name: str
    success: bool
    report: BriefingReport | None = None
    score: StartupScore | None = None
    error: str | None = None


async def _run_one(name: str, urls: list[str], model: str, sem: asyncio.Semaphore) -> BatchResult:
    async with sem:
        try:
            pipeline = build_pipeline()
            state = await pipeline.ainvoke({
                "startup_name": name,
                "urls": urls,
                "model": model,
                "startup": None,
                "recommendations": [],
                "briefing": None,
                "error": None,
            })

            if state.get("error") or not state.get("briefing"):
                return BatchResult(startup_name=name, success=False, error=state.get("error", "Pipeline falhou"))

            report: BriefingReport = state["briefing"]

            score = await score_startup(report, model=model)

            return BatchResult(startup_name=name, success=True, report=report, score=score)

        except Exception as e:
            return BatchResult(startup_name=name, success=False, error=str(e))


async def run_batch(
    startups: list[str],
    urls_map: dict[str, list[str]] | None = None,
    model: str = DEFAULT_MODEL,
    concurrency: int = 2,
) -> list[BatchResult]:
    """
    startups: lista de nomes
    urls_map: {nome: [urls]} opcional — se ausente usa researcher
    concurrency: max análises simultâneas (default 2, conservador pro rate limit)
    """
    sem = asyncio.Semaphore(concurrency)
    urls_map = urls_map or {}

    tasks = [
        _run_one(name, urls_map.get(name, []), model, sem)
        for name in startups
    ]

    return await asyncio.gather(*tasks)
