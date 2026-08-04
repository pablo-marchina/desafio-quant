from __future__ import annotations

from typing import Any

from agents.nvidia.competitive.common import call_json
from agents.nvidia.state import AgentState
from scraper.enrichment_pipeline import config
from scraper.enrichment_pipeline import main as enrichment_main
from scraper.enrichment_pipeline.nodes import update_supabase


DETECTION_PROMPT = """
Analise o pedido do usuário. Identifique se ele fala de uma startup específica
e extraia apenas o nome explicitamente informado. Classifique a ação:
- competitive: pede comparação com big techs/concorrentes;
- recommendation: pede sugestão/recomendação/match de produto NVIDIA;
- rag: consulta sobre a startup sem pedir recomendação ou comparação.
Se pedir recomendação e comparação, use competitive.
Nunca invente nome. Retorne somente JSON:
{"startup_mencionada":bool,"startup_nome":string|null,
 "acao":"rag|recommendation|competitive"}.
""".strip()


def detect_startup_request(question: str) -> dict[str, Any]:
    result = call_json(DETECTION_PROMPT, {"pergunta": question})
    action = str(result.get("acao") or "rag")
    if action not in {"rag", "recommendation", "competitive"}:
        action = "rag"
    name = str(result.get("startup_nome") or "").strip() or None
    mentioned = result.get("startup_mencionada") is True and bool(name)
    return {
        "startup_mencionada": mentioned,
        "startup_nome": name if mentioned else None,
        "acao": action,
    }


def _query_rows(
    table: str, name: str, *, exact: bool, candidate_id: str | None = None
) -> list[dict[str, Any]]:
    if update_supabase._has_rest_credentials():
        params: dict[str, Any] = {"select": "*", "limit": "5"}
        if candidate_id:
            params["candidate_id"] = f"eq.{candidate_id}"
        elif exact:
            params["company_name"] = f"ilike.{name}"
        else:
            params["company_name"] = f"ilike.*{name}*"
        response = update_supabase._request("GET", params=params, table=table)
        payload = response.json()
        return list(payload if isinstance(payload, list) else [])

    with update_supabase._pg_connect() as connection:
        try:
            import psycopg2.extras

            cursor_factory = psycopg2.extras.RealDictCursor
        except ModuleNotFoundError:  # pragma: no cover
            cursor_factory = None
        with connection.cursor(cursor_factory=cursor_factory) as cursor:
            if candidate_id:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE candidate_id = %s LIMIT 5",
                    (candidate_id,),
                )
            elif exact:
                cursor.execute(
                    f"SELECT * FROM {table} "
                    "WHERE LOWER(company_name) = LOWER(%s) LIMIT 5",
                    (name,),
                )
            else:
                cursor.execute(
                    f"SELECT * FROM {table} "
                    "WHERE company_name ILIKE %s ORDER BY updated_at DESC LIMIT 5",
                    (f"%{name}%",),
                )
            rows = cursor.fetchall()
            if cursor_factory:
                return [dict(row) for row in rows]
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in rows]


def find_startup_candidate(name: str) -> tuple[str, dict[str, Any] | None]:
    rows = _query_rows(config.SUPABASE_TABLE, name, exact=True)
    if not rows:
        rows = _query_rows(config.SUPABASE_TABLE, name, exact=False)
    if not rows:
        return "nao_encontrada", None
    if len(rows) > 1:
        return "ambiguo", None
    return "encontrada", rows[0]


def load_enriched_startup(candidate_id: str) -> dict[str, Any] | None:
    rows = _query_rows(
        config.ENRICHMENT_RESULTS_TABLE,
        "",
        exact=True,
        candidate_id=candidate_id,
    )
    return rows[0] if rows else None


def _startup_context(
    candidate: dict[str, Any], enriched: dict[str, Any] | None
) -> dict[str, Any]:
    record = enriched or candidate
    company = str(record.get("company_name") or candidate.get("company_name") or "")
    url = str(
        record.get("validated_url")
        or record.get("website")
        or candidate.get("website_url")
        or candidate.get("website")
        or ""
    )
    description = str(
        record.get("company_description")
        or record.get("description")
        or candidate.get("description")
        or ""
    )
    tech_stack = list(record.get("tech_stack") or [])
    github_audit = {
        "status": str(
            record.get("github_validacao_status") or "nao_documentado"
        ),
        "tentativas": int(record.get("github_tentativas") or 0),
        "candidatos_testados": list(
            record.get("github_candidatos_testados") or []
        ),
        "repo_validado": record.get("github_repo_validado"),
        "evidencia": record.get("github_validacao_evidencia"),
        "criterios": list(record.get("github_validacao_criterios") or []),
    }
    insufficient = []
    if not tech_stack:
        insufficient.append(
            "Stack atual não documentada. "
            f"GitHub Discovery: status={github_audit['status']}, "
            f"tentativas={github_audit['tentativas']}, "
            f"candidatos={len(github_audit['candidatos_testados'])}."
        )
    source = url or "Supabase"
    strengths: list[dict[str, str]] = []
    if description:
        strengths.append(
            {
                "aspecto": "Serviço documentado",
                "evidencia": description,
                "fonte": source,
            }
        )
    if tech_stack:
        strengths.append(
            {
                "aspecto": "Stack técnica documentada",
                "evidencia": ", ".join(map(str, tech_stack)),
                "fonte": source,
            }
        )
    return {
        "empresa": company,
        "segmento": str(
            record.get("target_market") or candidate.get("segment") or ""
        ),
        "dor_resolvida": description,
        "servico_startup_analisado": description,
        "stack_atual": tech_stack,
        "pontos_fortes": strengths,
        "gaps_identificados": [],
        "recomendacoes_nvidia": [],
        "startup_url": url,
        "github_discovery": github_audit,
        "dados_insuficientes": insufficient,
    }


def startup_context_agent(state: AgentState) -> dict[str, Any]:
    question = state["question"]
    if state.get("startup_context_preloaded"):
        description = str(
            state.get("servico_startup_analisado")
            or state.get("dor_resolvida")
            or ""
        )
        stack = list(state.get("stack_atual") or [])
        return {
            "original_question": question,
            "startup_mencionada": True,
            "startup_lookup_status": "encontrada",
            "rag_question": (
                f"{question}\n\n"
                "Contexto verificado da startup no Supabase:\n"
                f"Empresa: {state.get('empresa') or ''}\n"
                f"Descrição: {description}\n"
                f"Stack: {', '.join(stack) or 'não documentada'}"
            ),
        }
    try:
        detection = detect_startup_request(question)
    except Exception as error:
        return {
            "startup_lookup_status": "erro",
            "final_answer": f"Não foi possível interpretar a startup: {error}",
        }

    update: dict[str, Any] = {
        "original_question": question,
        "startup_mencionada": detection["startup_mencionada"],
        "startup_nome_detectado": detection["startup_nome"],
        "output_mode": (
            detection["acao"]
            if detection["startup_mencionada"]
            else state.get("output_mode", "briefing")
        ),
    }
    if not detection["startup_mencionada"]:
        update["startup_lookup_status"] = "nao_aplicavel"
        return update

    try:
        status, candidate = find_startup_candidate(detection["startup_nome"])
    except Exception as error:
        return {
            **update,
            "startup_lookup_status": "erro",
            "final_answer": f"Falha ao consultar o Supabase: {error}",
        }
    if status == "nao_encontrada":
        return {
            **update,
            "startup_lookup_status": status,
            "final_answer": (
                f'A startup "{detection["startup_nome"]}" não foi encontrada '
                "no Supabase."
            ),
        }
    if status == "ambiguo":
        return {
            **update,
            "startup_lookup_status": status,
            "final_answer": (
                f'O nome "{detection["startup_nome"]}" corresponde a mais de '
                "uma startup no Supabase. Informe o nome completo."
            ),
        }

    assert candidate is not None
    candidate_id = str(candidate.get("id") or "")
    try:
        update_supabase.ensure_results_schema()
        enrichment_main.run(
            company_id=candidate_id,
            mode="full",
            no_cache=True,
        )
        enriched = load_enriched_startup(candidate_id)
    except Exception as error:
        return {
            **update,
            "startup_lookup_status": "erro",
            "startup_candidate_id": candidate_id,
            "startup_supabase_record": candidate,
            "final_answer": f"Falha ao enriquecer a startup selecionada: {error}",
        }

    context = _startup_context(candidate, enriched)
    if (
        detection["acao"] == "competitive"
        and not context["servico_startup_analisado"]
    ):
        return {
            **update,
            **context,
            "startup_lookup_status": "erro",
            "startup_candidate_id": candidate_id,
            "startup_supabase_record": candidate,
            "startup_enrichment_record": enriched,
            "final_answer": (
                "A startup foi encontrada, mas o Supabase não possui descrição "
                "suficiente do serviço para uma comparação competitiva."
            ),
        }
    rag_question = (
        f"{question}\n\nContexto verificado da startup no Supabase:\n"
        f"Empresa: {context['empresa']}\n"
        f"Descrição: {context['dor_resolvida']}\n"
        f"Stack: {', '.join(context['stack_atual']) or 'não documentada'}"
    )
    return {
        **update,
        **context,
        "startup_lookup_status": "encontrada",
        "startup_candidate_id": candidate_id,
        "startup_supabase_record": candidate,
        "startup_enrichment_record": enriched,
        "rag_question": rag_question,
    }


def route_after_startup_context(state: AgentState) -> str:
    return (
        "end"
        if state.get("startup_lookup_status")
        in {"nao_encontrada", "ambiguo", "erro"}
        else "rag"
    )
