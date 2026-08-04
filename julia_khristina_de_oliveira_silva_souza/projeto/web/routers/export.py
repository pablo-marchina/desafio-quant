import json
import csv
import io
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pipeline.db.connection import fetch_one, fetch_all

router = APIRouter(tags=["export"])


@router.get("/export/briefing/{briefing_id}")
def export_briefing(briefing_id: str, formato: str = Query("json", pattern="^(json|csv)$")):
    briefing = fetch_one(
        "SELECT * FROM briefings WHERE id = ?", (briefing_id,)
    )
    if not briefing:
        return {"erro": "Briefing não encontrado"}, 404

    if formato == "json":
        conteudo = briefing.get("conteudo_json")
        if isinstance(conteudo, str):
            conteudo = json.loads(conteudo)
        return StreamingResponse(
            iter([json.dumps(conteudo, ensure_ascii=False, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=briefing_{briefing_id}.json"}
        )

    if formato == "csv":
        startup = fetch_one("SELECT * FROM startups WHERE id = ?", (briefing["startup_id"],))
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["campo", "valor"])
        if startup:
            for k, v in startup.items():
                writer.writerow([k, str(v) if v else ""])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=briefing_{briefing_id}.csv"}
        )

    return {"erro": "Formato não suportado"}, 400


@router.get("/export/startups")
def export_startups(formato: str = Query("csv", pattern="^(csv)$")):
    startups = fetch_all("""
        SELECT s.nome, s.setor, s.cidade, s.estagio, s.website,
               c.ai_classification, c.score_fit_nvidia,
               c.nvidia_techs_detectadas as techs_recomendadas
        FROM startups s
        LEFT JOIN classificacoes c ON c.startup_id = s.id
        ORDER BY c.score_fit_nvidia DESC
    """)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["nome", "setor", "cidade", "estagio", "website", "classificacao", "score_fit", "techs_recomendadas"])
    for s in startups:
        writer.writerow([
            s.get("nome", ""), s.get("setor", ""), s.get("cidade", ""),
            s.get("estagio", ""), s.get("website", ""), s.get("ai_classification", ""),
            s.get("score_fit_nvidia", ""), s.get("techs_recomendadas", "")
        ])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=startups_export.csv"}
    )
