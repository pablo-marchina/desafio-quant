from uuid import UUID

from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_startups() -> dict[str, list[object]]:
    return {"items": []}


@router.get("/{startup_id}")
def read_startup(startup_id: UUID) -> dict[str, object]:
    return {"id": str(startup_id)}


@router.get("/{startup_id}/evidence")
def list_startup_evidence(startup_id: UUID) -> dict[str, object]:
    return {"startup_id": str(startup_id), "items": []}


@router.get("/{startup_id}/recommendations")
def list_startup_recommendations(startup_id: UUID) -> dict[str, object]:
    return {"startup_id": str(startup_id), "items": []}
