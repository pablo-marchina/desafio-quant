from fastapi import APIRouter
from pipeline.db.connection import fetch_one

router = APIRouter(tags=["briefings"])


@router.get("/startups/{startup_id}/briefing")
def get_briefing(startup_id: str):
    briefing = fetch_one(
        "SELECT * FROM briefings WHERE startup_id = ? ORDER BY gerado_em DESC LIMIT 1",
        (startup_id,)
    )
    if not briefing:
        return {"erro": "Briefing não encontrado"}, 404
    return briefing


@router.get("/briefings/{briefing_id}")
def get_briefing_by_id(briefing_id: str):
    briefing = fetch_one("SELECT * FROM briefings WHERE id = ?", (briefing_id,))
    if not briefing:
        return {"erro": "Briefing não encontrado"}, 404
    return briefing
