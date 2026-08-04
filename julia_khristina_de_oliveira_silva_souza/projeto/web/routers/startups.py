from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from pipeline.db.connection import execute_query, fetch_all, fetch_one
from pipeline.agents.email_writer import gerar_email
from pipeline.utils.validation import validar_email, validar_formato_email, validar_cidade, normalizar_cidade
from datetime import datetime, timezone
from typing import Optional


class StartupUpdate(BaseModel):
    nome: Optional[str] = None
    website: Optional[str] = None
    setor: Optional[str] = None
    descricao: Optional[str] = None
    produto_principal: Optional[str] = None
    cidade: Optional[str] = None
    estagio: Optional[str] = None
    email_contato: Optional[str] = None

router = APIRouter(tags=["startups"])


@router.get("/startups")
def listar_startups(
    setor: str | None = None,
    classificacao: str | None = None,
    score_fit_min: float | None = None,
    contato: str | None = None,
    completude: str | None = None,
    pais: str = "Brasil",
    order_by: str = "score_fit_nvidia",
    limit: int = 50,
    offset: int = 0
):
    conditions = ["s.pais = ?"]
    params: list = [pais]

    if setor:
        conditions.append("s.setor = ?")
        params.append(setor)
    if classificacao:
        conditions.append("c.ai_classification = ?")
        params.append(classificacao)
    if score_fit_min:
        conditions.append("c.score_fit_nvidia >= ?")
        params.append(score_fit_min)
    if contato == "sim":
        conditions.append("s.email_enviado_em IS NOT NULL")
    elif contato == "nao":
        conditions.append("s.email_enviado_em IS NULL")
    if completude == "incompletas":
        conditions.append("(s.email_contato IS NULL OR s.email_contato = '' OR s.cidade IS NULL OR s.cidade = '')")
    elif completude == "completas":
        conditions.append("(s.email_contato IS NOT NULL AND s.email_contato != '' AND s.cidade IS NOT NULL AND s.cidade != '')")

    where = " AND ".join(conditions)

    query = f"""
        SELECT s.id, s.nome, s.website, s.setor, s.cidade, s.estagio,
               s.email_contato, s.email_enviado_em,
               c.ai_classification, c.score_fit_nvidia, c.usa_nvidia
        FROM startups s
        LEFT JOIN classificacoes c ON c.id = (
            SELECT id FROM classificacoes
            WHERE startup_id = s.id
            ORDER BY classificado_em DESC
            LIMIT 1
        )
        WHERE {where}
        ORDER BY c.{order_by} DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = fetch_all(query, tuple(params))
    return {"startups": rows, "total": len(rows)}


@router.patch("/startups/{startup_id}/marcar-contato")
def marcar_contato(startup_id: str, email: str | None = None):
    startup = fetch_one("SELECT id FROM startups WHERE id = ?", (startup_id,))
    if not startup:
        return {"erro": "Startup não encontrada"}, 404
    if email:
        if not validar_formato_email(email):
            return {"erro": "Email inválido. Use o formato usuario@dominio.com"}, 400
        email_valido, erro = validar_email(email)
        if not email_valido:
            return {"erro": f"Email inválido: {erro}"}, 400
    agora = datetime.now(timezone.utc).isoformat()
    if email:
        execute_query(
            "UPDATE startups SET email_contato = ?, email_enviado_em = ? WHERE id = ?",
            (email, agora, startup_id)
        )
    else:
        execute_query(
            "UPDATE startups SET email_enviado_em = ? WHERE id = ?",
            (agora, startup_id)
        )
    return {"ok": True, "email_enviado_em": agora}


@router.patch("/startups/{startup_id}")
def atualizar_startup(startup_id: str, data: StartupUpdate):
    startup = fetch_one("SELECT id FROM startups WHERE id = ?", (startup_id,))
    if not startup:
        return {"erro": "Startup não encontrada"}, 404

    updates = []
    params = []

    if data.email_contato is not None:
        if not validar_formato_email(data.email_contato):
            return {"erro": "Email inválido. Use o formato usuario@dominio.com"}, 400
        valido, erro = validar_email(data.email_contato)
        if not valido:
            return {"erro": f"Email inválido: {erro}"}, 400
        updates.append("email_contato = ?")
        params.append(data.email_contato)

    if data.cidade is not None:
        valido, normalizada = validar_cidade(data.cidade)
        if valido:
            updates.append("cidade = ?")
            params.append(normalizada)
        else:
            normalizada = normalizar_cidade(data.cidade)
            updates.append("cidade = ?")
            params.append(normalizada)

    for campo in ["nome", "website", "setor", "descricao", "produto_principal", "estagio"]:
        valor = getattr(data, campo, None)
        if valor is not None:
            updates.append(f"{campo} = ?")
            params.append(valor)

    if not updates:
        return {"erro": "Nenhum campo para atualizar"}, 400

    updates.append("updated_at = datetime('now')")
    params.append(startup_id)
    execute_query(
        f"UPDATE startups SET {', '.join(updates)} WHERE id = ?",
        tuple(params)
    )
    return {"ok": True}


@router.post("/startups/{startup_id}/gerar-email")
def gerar_email_endpoint(startup_id: str):
    resultado = gerar_email(startup_id)
    if "erro" in resultado:
        return resultado, 502
    return resultado


@router.get("/startups/{startup_id}")
def detalhe_startup(startup_id: str):
    startup = fetch_one("SELECT * FROM startups WHERE id = ?", (startup_id,))
    if not startup:
        return {"erro": "Startup não encontrada"}, 404

    classificacao = fetch_one(
        "SELECT * FROM classificacoes WHERE startup_id = ? ORDER BY classificado_em DESC LIMIT 1",
        (startup_id,)
    )
    evidencias = fetch_all(
        "SELECT * FROM evidencias WHERE startup_id = ? ORDER BY score_qualidade DESC LIMIT 10",
        (startup_id,)
    )
    recomendacoes = fetch_all(
        "SELECT * FROM recomendacoes WHERE startup_id = ? ORDER BY rank ASC",
        (startup_id,)
    )
    briefing = fetch_one(
        "SELECT id, gerado_em FROM briefings WHERE startup_id = ? ORDER BY gerado_em DESC LIMIT 1",
        (startup_id,)
    )

    return {
        "startup": startup,
        "classificacao": classificacao,
        "evidencias": evidencias,
        "recomendacoes": recomendacoes,
        "briefing_id": briefing["id"] if briefing else None
    }
