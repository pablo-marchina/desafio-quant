from typing import TypedDict


class StartupAnalysisState(TypedDict, total=False):
    run_id: str
    query: str
    startup_url: str
    source_document_ids: list[str]
    startup_id: str
    assessment_id: str
    recommendation_ids: list[str]
    briefing_id: str
    errors: list[str]
