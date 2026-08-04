from __future__ import annotations

from typing import Any

from agents.nvidia.competitive.common import call_json
from agents.nvidia.state import AgentState

GAP_SIGNALS = (
    "precisa",
    "necessita",
    "problema",
    "limitação",
    "limitacao",
    "falta",
    "ausência",
    "ausencia",
    "gargalo",
    "reduzir",
    "melhorar",
    "latência",
    "latencia",
    "custo",
    "segurança",
    "seguranca",
    "needs",
    "missing",
    "lack",
    "problem",
    "bottleneck",
    "reduce",
    "latency",
)


GAP_PROMPT = """
Identifique gaps ATUAIS da startup usando apenas evidências fornecidas.
Um gap existe somente quando a pergunta do usuário ou uma fonte da startup
declara explicitamente uma necessidade, limitação, ausência ou problema.
Ausência de dados, stack não documentada e características genéricas do setor
NÃO são gaps técnicos. Não use recomendações NVIDIA para inferir gaps.
Retorne json:
{"gaps_identificados":[
  {"gap":"...","evidencia":"trecho exato ou paráfrase fiel","fonte":"..."}
]}.
Se nenhum gap estiver documentado, retorne lista vazia.
""".strip()


def gap_analysis_agent(state: AgentState) -> dict[str, Any]:
    if not (state.get("startup_mencionada") or state.get("empresa")):
        return {}
    documented_need = str(state.get("user_documented_need") or "").strip()
    if documented_need:
        company = str(state.get("empresa") or "A startup")
        return {
            "gaps_identificados": [
                {
                    "gap": documented_need,
                    "evidencia": f"{company} precisa {documented_need}.",
                    "fonte": "Necessidade informada pelo usuário",
                }
            ]
        }
    allowed_sources = {"Pergunta do usuário"}
    source_evidence = {
        "Pergunta do usuário": str(
            state.get("original_question") or state.get("question") or ""
        )
    }
    startup_evidence = []
    for point in state.get("pontos_fortes", []):
        if not isinstance(point, dict):
            continue
        source = str(point.get("fonte") or "")
        if source:
            allowed_sources.add(source)
            source_evidence[source] = (
                source_evidence.get(source, "")
                + " "
                + str(point.get("evidencia") or "")
            )
        startup_evidence.append(point)
    result = call_json(
        GAP_PROMPT,
        {
            "pergunta_usuario": state.get("original_question")
            or state.get("question"),
            "estado_atual_startup": {
                "empresa": state.get("empresa"),
                "descricao": state.get("dor_resolvida"),
                "stack_atual": state.get("stack_atual", []),
                "evidencias": startup_evidence,
            },
        },
    )
    gaps = []
    for item in result.get("gaps_identificados", []):
        source = str(item.get("fonte") or "") if isinstance(item, dict) else ""
        evidence = (
            str(item.get("evidencia") or "") if isinstance(item, dict) else ""
        )
        source_text = source_evidence.get(source, "")
        if (
            isinstance(item, dict)
            and str(item.get("gap") or "").strip()
            and evidence.strip()
            and source in allowed_sources
            and evidence.casefold() in source_text.casefold()
            and any(signal in evidence.casefold() for signal in GAP_SIGNALS)
        ):
            gaps.append(
                {
                    "gap": str(item["gap"]).strip(),
                    "evidencia": evidence.strip(),
                    "fonte": source,
                }
            )
    update: dict[str, Any] = {"gaps_identificados": gaps}
    if not gaps:
        insufficient = list(state.get("dados_insuficientes", []))
        insufficient.append(
            "Nenhum gap atual da startup está explicitamente documentado."
        )
        update["dados_insuficientes"] = list(dict.fromkeys(insufficient))
    return update
