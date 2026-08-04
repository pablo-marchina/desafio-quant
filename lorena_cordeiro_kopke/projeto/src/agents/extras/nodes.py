from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client as SupabaseClient
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

from agents.extras.gemini import chamar_gemini  # noqa: E402
from agents.extras.prompts import (  # noqa: E402
    PROMPT_KIT_INICIO,
    PROMPT_NEGOCIO,
    PROMPT_ROADMAP,
    PROMPT_SINTESE_EXECUTIVA,
    PROMPT_TECNICO,
)
from agents.extras.state import EstadoRecomendacao  # noqa: E402
from agents.query import gerar_query, resolver_setor_qdrant  # noqa: E402
from rag.buscador import buscar  # noqa: E402

logger = logging.getLogger(__name__)

_LIMIAR_QUALIDADE = -3.0


def _extrair_json(texto: str) -> str:
    """Extrai JSON de dentro de blocos markdown (```json ... ```) ou retorna o texto limpo.

    Cobre o caso mais comum de desobediência de instrução do LLM: texto introdutório
    seguido de bloco de código. Um strip linha-a-linha não é suficiente porque deixa
    o texto antes da fence, quebrando json.loads.
    """
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    return texto.strip()


# ── Utilitário Supabase ───────────────────────────────────────────────────────

_supabase_instance: SupabaseClient | None = None
_supabase_lock = threading.Lock()


def _get_supabase() -> SupabaseClient:
    global _supabase_instance
    if _supabase_instance is None:
        with _supabase_lock:
            if _supabase_instance is None:  # double-checked locking — mesmo padrão de gemini.py
                _supabase_instance = create_client(
                    os.environ["SUPABASE_URL"],
                    os.environ["SUPABASE_KEY"],
                )
    return _supabase_instance


# ── Nó 1: carregar_perfil ─────────────────────────────────────────────────────

def carregar_perfil(estado: EstadoRecomendacao) -> dict:
    """Carrega o perfil completo da startup do Supabase e inicializa todo o estado."""
    _estado_inicial = {
        "query":             "",
        "iteracao_busca":    0,
        "iteracao_json":     0,
        "chunks":            [],
        "chunks_refs":       [],
        "explicacao":        None,
        "resposta_bruta":    "",
        "erro_json":         "",
        "sintese_executiva": None,
        "roadmap":           None,
        "kit_inicio":        None,
        "output_final":      None,
    }
    try:
        supabase = _get_supabase()
        empresa = (
            supabase.table("empresas_uso_ia")
            .select(
                "empresa_id, produto, uso_ia_descricao, ia_e_core_product, "
                "ia_tipo, setor, nivel_maturidade_ia, score_maturidade_ia, "
                "produto_ia_lancado, modelo_negocio, mercado_alvo, ano_fundacao, "
                "cnae_principal"
            )
            .eq("empresa_id", estado["empresa_id"])
            .single()
            .execute()
            .data
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] falha ao carregar perfil do Supabase: %s", estado["empresa_id"], exc)
        # iteracao_busca=3 força rotear_apos_busca → sem_resultado sem executar buscas
        return {**_estado_inicial, "perfil": {}, "iteracao_busca": 3}

    return {**_estado_inicial, "perfil": empresa}


# ── Nó 2: montar_query ────────────────────────────────────────────────────────

def montar_query(estado: EstadoRecomendacao) -> dict:
    """Gera a query semântica a partir do perfil usando LLM com fallback determinístico."""
    if not estado.get("perfil"):
        logger.warning("[%s] perfil vazio — query não gerada", estado["empresa_id"])
        return {"query": ""}

    perfil = estado["perfil"]
    try:
        query = gerar_query({
            "setor":            perfil.get("setor"),
            "produto":          perfil.get("produto"),
            "ia_tipo":          perfil.get("ia_tipo"),
            "uso_ia_descricao": perfil.get("uso_ia_descricao"),
            "maturidade":       perfil.get("nivel_maturidade_ia"),
            "ia_core_product":  perfil.get("ia_e_core_product"),
        })
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] falha ao gerar query: %s — usando fallback local", estado["empresa_id"], exc)
        partes = [v for v in [
            perfil.get("setor"), perfil.get("produto"), perfil.get("ia_tipo"),
        ] if v]
        query = " ".join(partes) if partes else ""

    logger.info("[%s] query montada: %s", estado["empresa_id"], query)
    return {"query": query}


# ── Nó 3: buscar_e_reranquear ─────────────────────────────────────────────────

def buscar_e_reranquear(estado: EstadoRecomendacao) -> dict:
    """Busca vetorial no Qdrant + reranking com relaxamento progressivo por iteração."""
    iteracao = estado.get("iteracao_busca", 0)

    # Perfil vazio significa que carregar_perfil falhou — não adianta buscar
    if not estado.get("perfil"):
        logger.warning("[%s] perfil vazio — busca abortada", estado["empresa_id"])
        return {"chunks": [], "chunks_refs": [], "iteracao_busca": iteracao + 1}

    # Query vazia significa que montar_query falhou ou não gerou conteúdo útil
    if not estado.get("query", "").strip():
        logger.warning("[%s] query vazia — busca abortada", estado["empresa_id"])
        return {"chunks": [], "chunks_refs": [], "iteracao_busca": iteracao + 1}

    # Iteração 0: 3× candidatos + filtro de setor
    # Iteração 1+: candidatos crescem e filtro de setor é removido
    fator = 3 + iteracao * 2  # iter 0: ×3 / iter 1: ×5 / iter 2: ×7
    filtros: dict = (
        {}
        if iteracao >= 1
        else {"setor": {"$in": resolver_setor_qdrant(estado["perfil"].get("setor"))}}
    )

    logger.info(
        "[%s] busca — iteracao=%d fator=%d filtros=%s",
        estado["empresa_id"], iteracao, fator, filtros,
    )

    try:
        chunks = buscar(
            query=estado["query"],
            filtros=filtros,
            top_k=5,
            reranking=True,
            fator_candidatos=fator,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[%s] erro na busca (iteracao=%d): %s",
            estado["empresa_id"], iteracao, exc,
        )
        # Lista vazia → rotear_apos_busca ativa o ciclo de retry ou sem_resultado
        return {"chunks": [], "chunks_refs": [], "iteracao_busca": iteracao + 1}

    # Referências leves para persistência e LLMs 2-4 (sem o campo texto)
    chunks_refs = [
        {
            "tecnologia":   c.get("tecnologia"),
            "url":          c.get("url"),
            "chunk_index":  c.get("chunk_index"),
            "rerank_score": round(c.get("rerank_score", c.get("score", 0.0)), 4),
        }
        for c in chunks
    ]

    return {
        "chunks":         chunks,
        "chunks_refs":    chunks_refs,
        "iteracao_busca": iteracao + 1,
    }


# ── Função de roteamento pós-busca ────────────────────────────────────────────

def rotear_apos_busca(estado: EstadoRecomendacao) -> str:
    """
    Funde o ciclo de qualidade dos chunks com o roteamento por perfil.
    Um único add_conditional_edges é obrigatório — LangGraph sobrescreve silenciosamente
    um segundo conditional edge do mesmo nó fonte.
    """
    chunks = estado.get("chunks", [])
    iteracao = estado.get("iteracao_busca", 0)

    if not chunks:
        return "re_buscar" if iteracao < 3 else "sem_resultado"

    # Default 0.0 (conservador) — se rerank_score não existir, força o ciclo de qualidade
    # em vez de deixar chunks ruins passarem silenciosamente para o LLM.
    score_top = chunks[0].get("rerank_score", 0.0)

    if score_top < _LIMIAR_QUALIDADE:
        if iteracao < 3:
            return "re_buscar"
        # Esgotou retries com qualidade insuficiente — não passa chunks ruins ao LLM
        logger.warning(
            "[%s] qualidade insuficiente após %d buscas (score=%.3f) — sem_resultado",
            estado["empresa_id"], iteracao, score_top,
        )
        return "sem_resultado"

    if estado["perfil"].get("ia_e_core_product"):
        return "explicar_tecnico"
    return "explicar_negocio"


# ── Nó 4a: explicar_tecnico ───────────────────────────────────────────────────

def explicar_tecnico(estado: EstadoRecomendacao) -> dict:
    """LLM 1 — foco em stack técnica. Usado quando ia_e_core_product = True."""
    prompt = PROMPT_TECNICO.format(
        perfil=estado["perfil"],
        chunks=estado["chunks"],
    )
    if estado.get("erro_json"):
        prompt += (
            f"\n\nATENÇÃO: sua resposta anterior falhou no parse JSON com o erro: "
            f"{estado['erro_json']}\nRetorne APENAS JSON válido, sem markdown."
        )
    resposta = chamar_gemini(prompt)
    # chunks NÃO é esvaziado aqui — validar_json libera a memória apenas no sucesso,
    # para que retries ainda tenham acesso ao conteúdo dos chunks.
    return {"resposta_bruta": resposta}


# ── Nó 4b: explicar_negocio ───────────────────────────────────────────────────

def explicar_negocio(estado: EstadoRecomendacao) -> dict:
    """LLM 1 — foco em casos de uso de negócio. Usado quando ia_e_core_product = False."""
    prompt = PROMPT_NEGOCIO.format(
        perfil=estado["perfil"],
        chunks=estado["chunks"],
    )
    if estado.get("erro_json"):
        prompt += (
            f"\n\nATENÇÃO: sua resposta anterior falhou no parse JSON com o erro: "
            f"{estado['erro_json']}\nRetorne APENAS JSON válido, sem markdown."
        )
    resposta = chamar_gemini(prompt)
    # chunks NÃO é esvaziado aqui — validar_json libera a memória apenas no sucesso,
    # para que retries ainda tenham acesso ao conteúdo dos chunks.
    return {"resposta_bruta": resposta}


# ── Nó 5: validar_json ────────────────────────────────────────────────────────

def validar_json(estado: EstadoRecomendacao) -> dict:
    """Tenta parsear a resposta bruta do LLM 1. Incrementa iteracao_json apenas em falha."""
    texto = _extrair_json(estado.get("resposta_bruta", ""))

    try:
        parsed = json.loads(texto)
        return {
            "explicacao":    parsed,
            "erro_json":     "",
            "iteracao_json": estado.get("iteracao_json", 0),  # não incrementa em sucesso
            "chunks":        [],  # libera texto dos chunks — LLMs 2-4 não precisam do conteúdo
        }
    except json.JSONDecodeError as exc:
        logger.warning(
            "[%s] JSON inválido (iteracao_json=%d): %s",
            estado["empresa_id"], estado.get("iteracao_json", 0), exc,
        )
        return {
            "explicacao":    None,
            "erro_json":     str(exc),
            "iteracao_json": estado.get("iteracao_json", 0) + 1,  # sempre incrementa em falha
            # chunks preservado intencionalmente — retry do LLM 1 ainda precisa dos textos
        }


# ── Função de roteamento pós-validação ───────────────────────────────────────

def checar_json_valido(estado: EstadoRecomendacao) -> str:
    """
    Fixes aplicados:
    - isinstance() em vez de truthiness para não tratar {} (dict vazio válido) como falha.
    - iteracao_json < 3 para garantir exatamente 2 retries (3 tentativas totais).
    """
    if isinstance(estado.get("explicacao"), dict) and not estado.get("erro_json"):
        return "valido"
    if estado.get("iteracao_json", 0) < 3:
        return "retry_tecnico" if estado["perfil"].get("ia_e_core_product") else "retry_negocio"
    return "falha"


# ── Nó 6: sintese_executiva ───────────────────────────────────────────────────

def sintese_executiva_node(estado: EstadoRecomendacao) -> dict:
    """LLM 2 — traduz a recomendação técnica para linguagem executiva (CEO + account manager)."""
    prompt = PROMPT_SINTESE_EXECUTIVA.format(
        perfil=estado["perfil"],
        explicacao=estado["explicacao"],
    )
    resposta = chamar_gemini(prompt)
    try:
        return {"sintese_executiva": json.loads(_extrair_json(resposta))}
    except json.JSONDecodeError:
        logger.warning("[%s] sintese_executiva: JSON inválido — armazenando texto bruto", estado["empresa_id"])
        return {"sintese_executiva": {"texto_bruto": resposta}}


# ── Nó 7: roadmap_adocao ─────────────────────────────────────────────────────

def roadmap_adocao_node(estado: EstadoRecomendacao) -> dict:
    """LLM 3 — plano 30/60/90 dias para a tecnologia prioritária, calibrado pela maturidade."""
    perfil = estado["perfil"]
    prompt = PROMPT_ROADMAP.format(
        explicacao=estado["explicacao"],
        nivel_maturidade_ia=perfil.get("nivel_maturidade_ia", "não informado"),
        score_maturidade_ia=perfil.get("score_maturidade_ia", "?"),
        produto_ia_lancado=perfil.get("produto_ia_lancado", "não informado"),
        ia_tipo=perfil.get("ia_tipo", "não informado"),
        setor=perfil.get("setor", "não informado"),
    )
    resposta = chamar_gemini(prompt)
    try:
        return {"roadmap": json.loads(_extrair_json(resposta))}
    except json.JSONDecodeError:
        logger.warning("[%s] roadmap_adocao: JSON inválido — armazenando texto bruto", estado["empresa_id"])
        return {"roadmap": {"texto_bruto": resposta}}


# ── Nó 8: kit_inicio ─────────────────────────────────────────────────────────

def kit_inicio_node(estado: EstadoRecomendacao) -> dict:
    """LLM 4 — container NGC, tutorial e créditos Inception por tecnologia recomendada."""
    perfil = estado["perfil"]
    explicacao = estado.get("explicacao") or {}
    tecnologias = [t.get("tecnologia") for t in explicacao.get("tecnologias", [])]

    prompt = PROMPT_KIT_INICIO.format(
        tecnologias=tecnologias,
        ia_tipo=perfil.get("ia_tipo", "não informado"),
        nivel_maturidade_ia=perfil.get("nivel_maturidade_ia", "não informado"),
        score_maturidade_ia=perfil.get("score_maturidade_ia", "?"),
        produto_ia_lancado=perfil.get("produto_ia_lancado", "não informado"),
    )
    resposta = chamar_gemini(prompt)
    try:
        parsed = json.loads(_extrair_json(resposta))
        return {"kit_inicio": parsed.get("kit", [])}
    except json.JSONDecodeError:
        logger.warning("[%s] kit_inicio: JSON inválido — armazenando texto bruto", estado["empresa_id"])
        return {"kit_inicio": [{"texto_bruto": resposta}]}


# ── Nó 9: salvar_resultado ────────────────────────────────────────────────────

def salvar_resultado(estado: EstadoRecomendacao) -> dict:
    """
    Persiste todos os outputs no Supabase e seta output_final.
    try/except garante que falhas de DB não descartam os resultados LLM já gerados
    — o estado completo está preservado no checkpointer.
    """
    output = {
        "explicacao":        estado.get("explicacao"),
        "sintese_executiva": estado.get("sintese_executiva"),
        "roadmap":           estado.get("roadmap"),
        "kit_inicio":        estado.get("kit_inicio"),
    }
    try:
        supabase = _get_supabase()
        supabase.table("recomendacoes_nvidia").upsert(
            {
                "empresa_id":               estado["empresa_id"],
                "versao_base_conhecimento": date.today().isoformat(),
                "query":                    estado.get("query"),
                "chunks_reranqueados":      estado.get("chunks_refs", []),
                "explicacao":               estado.get("explicacao"),
                "sintese_executiva":        estado.get("sintese_executiva"),
                "roadmap":                  estado.get("roadmap"),
                "kit_inicio":               estado.get("kit_inicio"),
            },
            on_conflict="empresa_id",
        ).execute()
        logger.info("[%s] resultado salvo no Supabase", estado["empresa_id"])
    except Exception as exc:  # noqa: BLE001
        # Não re-raise: resultados estão no checkpointer e podem ser recuperados.
        logger.error("[%s] falha ao salvar no Supabase: %s", estado["empresa_id"], exc)

    return {"output_final": output}


# ── Nó 10: finalizar_sem_resultado ───────────────────────────────────────────

def finalizar_sem_resultado(estado: EstadoRecomendacao) -> dict:
    """Registra o motivo real da falha no output_final antes de encerrar o grafo."""
    if estado.get("iteracao_json", 0) >= 3:
        motivo = "JSON inválido após 3 tentativas"
    elif not estado.get("perfil"):
        motivo = "falha ao carregar perfil do Supabase"
    elif not estado.get("query", "").strip():
        motivo = "falha ao gerar query semântica"
    elif estado.get("chunks_refs"):
        # Houve chunks mas todos ficaram abaixo do limiar de qualidade
        score = estado["chunks_refs"][0].get("rerank_score", 0.0)
        motivo = f"qualidade insuficiente após 3 buscas (melhor rerank_score={score:.3f})"
    else:
        motivo = "nenhum chunk encontrado após 3 tentativas de busca"

    logger.warning("[%s] sem_resultado: %s", estado["empresa_id"], motivo)
    return {
        "output_final": {
            "erro":       motivo,
            "empresa_id": estado["empresa_id"],
        }
    }
