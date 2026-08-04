from fastapi import APIRouter, Query
from pipeline.agents.incomplete_reprocessor import reprocessar_incompletas

router = APIRouter(tags=["reprocess"])


@router.post("/reprocessar-incompletas")
def reprocessar(limite: int = Query(50, description="Número máximo de startups para reprocessar")):
    resultado = reprocessar_incompletas(limite=limite)
    return resultado
