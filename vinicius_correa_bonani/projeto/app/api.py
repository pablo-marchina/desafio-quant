"""API HTTP do Radar — expõe o banco/pipeline para o frontend React.

    uvicorn app.api:app --reload

FastAPI é fino: lê o que já existe (db) e devolve JSON. O front (Next, :3000) consome.
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app import db
from app.db import Descoberta, Empresa, SessionLocal

from pydantic import BaseModel
from app import batch
from app import discovery


app = FastAPI(title="NVIDIA Startup AI Radar API")

class AnalisarRequest(BaseModel):
    consulta: str


class DescobrirRequest(BaseModel):
    tema: str


# libera o front (Next em :3000) a chamar esta API (:8000) pelo navegador.
# Só vai importar no Passo 2, mas já deixamos pronto pra não esbarrar depois.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/empresas")
def listar_empresas() -> list[dict]:
    db.init_db()
    with SessionLocal() as sessao:
        empresas = sessao.query(Empresa).all()
        return [
            {
                "nome":e.nome,
                "setor": e.setor,
                "classificacao": e.classificacao,
                "score": e.score,
                "notas": e.notas,
                # quando a análise entrou no banco (p/ selo "nova" no ranking)
                "criado_em": e.created_at.isoformat() if e.created_at else None,
            }
            for e in empresas
        ]

@app.get("/empresas/{nome}")
def detalhe_empresa(nome: str) -> dict:
    db.init_db()
    with SessionLocal() as sessao:
        e = sessao.query(Empresa).filter_by(nome=nome).first()
        if e is None:
            raise HTTPException(status_code=404, detail=f"Empresa '{nome}' não encontrada")
        return {
            "nome": e.nome,
            "setor": e.setor,
            "descricao": e.descricao,
            "dados": e.dados,  # dump do DadosEmpresa: founders, funding, clientes, tecnologias
            "classificacao": e.classificacao,
            "score": e.score,
            "notas": e.notas,
            "recomendacao": e.recomendacao,
            "briefing": e.briefing,
            "fontes": e.fontes,
        }

@app.post("/analisar")
def analisar_empresa(req: AnalisarRequest) -> dict:
    batch.analisar(req.consulta)  # roda o grafo e persiste (~1-2 min)
    return {"ok": True, "consulta": req.consulta}


@app.post("/descobrir")
def descobrir_startups(req: DescobrirRequest) -> dict:
    """Tema → startups {nome, descricao} (busca web + LLM; lento, como /analisar).

    Só descobre; a análise é por item via /analisar. Cada pesquisa com
    resultado é gravada no histórico (tabela `descobertas`). Erros de
    busca/LLM viram lista vazia (o front trata como 'nada encontrado').
    """
    try:
        empresas = discovery.descobrir_detalhado(req.tema)
    except Exception:
        # loga no console do uvicorn (para diagnóstico) e devolve vazio,
        # que o front apresenta como "nada encontrado"
        import traceback

        traceback.print_exc()
        empresas = []

    if empresas:  # pesquisa vazia não polui o histórico
        db.init_db()
        with SessionLocal() as sessao:
            sessao.add(Descoberta(tema=req.tema, empresas=empresas))
            sessao.commit()

    return {"tema": req.tema, "empresas": empresas}


@app.get("/analisar-stream")
def analisar_empresa_stream(consulta: str) -> StreamingResponse:
    """Análise com progresso ao vivo, via SSE (Server-Sent Events).

    GET (não POST) porque o front conecta com EventSource, que só faz GET.
    Cada linha "data: {json}" é um evento: {"agente": ...} conforme cada nó
    do grafo roda, e {"done": true, ...} no fim (após persistir). Exceções
    viram um evento final com "erro" (o front fecha a conexão; sem isso o
    EventSource RECONECTA e re-dispararia a análise).
    """

    def eventos():
        try:
            for evento in batch.analisar_stream(consulta):
                yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback

            traceback.print_exc()
            falha = {"done": True, "erro": str(e)[:300]}
            yield f"data: {json.dumps(falha, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        # sem cache/buffering: cada evento precisa chegar na hora
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/descobertas")
def listar_descobertas() -> list[dict]:
    """Histórico das pesquisas da aba Descoberta (mais recentes primeiro)."""
    db.init_db()
    with SessionLocal() as sessao:
        registros = (
            sessao.query(Descoberta).order_by(Descoberta.criado_em.desc()).limit(20).all()
        )
        return [
            {
                "id": d.id,
                "tema": d.tema,
                "empresas": d.empresas,
                "criado_em": d.criado_em.isoformat() if d.criado_em else None,
            }
            for d in registros
        ]
