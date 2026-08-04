import os
import re
import json

from groq import Groq

from agents.nvidia.state import AgentState
from rag.settings import required_env

BRIEFING_PROMPT = """
Voce e um analista executivo especialista em NVIDIA.
Crie um briefing final curto, claro e acionavel usando somente a resposta RAG
e as recomendacoes fornecidas. Inclua: contexto, conclusoes principais,
recomendacao e pontos a validar. Toda afirmacao concreta deve citar [Fonte N].
Nao crie planos de implementacao, provas de conceito ou procedimentos.
Responda no idioma da pergunta. Nao introduza fatos, produtos, modelos,
comandos ou detalhes novos.
""".strip()

COMPETITIVE_BRIEFING_PROMPT = """
Voce e um analista executivo para o gerente de Startups & VCs da NVIDIA.
Consolide somente os dados fornecidos numa secao competitiva curta e acionavel.
Separe rigorosamente "estado atual" de "recomendação futura". A comparação
"quem entrega mais hoje" usa somente startup_estado_atual contra o serviço atual
da big tech; nunca escreva "startup + NVIDIA" nesse quadro.
Inclua obrigatoriamente: contexto verificado da startup; gaps documentados;
auditoria do GitHub Discovery; recomendacao NVIDIA
produzida pela Entrega 1; equivalente encontrado e fontes oficiais; pontos fortes
e fracos documentados de cada lado; quem entrega mais hoje; status dos dois
precos e analise de custo-beneficio; alavancagem NVIDIA e sua conexao explicita
com um gap da Entrega 1. Se a busca esgotou, declare a ausencia de equivalente e
liste dados insuficientes. Nao invente fatos nem preencha lacunas.
Responda no idioma da pergunta.
""".strip()


def clean_briefing(content: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()


def _truncate(value, limit: int = 800):
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, list):
        return [_truncate(item, limit) for item in value[:4]]
    if isinstance(value, dict):
        return {key: _truncate(item, limit) for key, item in value.items()}
    return value


def compact_competitive_payload(state: AgentState) -> dict:
    structured = state.get("structured_output") or {}
    startup = structured.get("startup_estado_atual") or {}
    delivery1 = structured.get("entrega1") or {}
    competitive = structured.get("comparacao_competitiva") or {}
    validated = competitive.get("servico_bigtech_validado") or {}
    content = validated.get("candidato_conteudo") or {}
    compact_validated = {
        "empresa": validated.get("candidato_empresa"),
        "url": validated.get("candidato_url"),
        "titulo": content.get("titulo_produto"),
        "trecho_relevante": content.get("trecho_relevante"),
        "categoria": validated.get("categoria_funcional_confirmada"),
        "modalidade": validated.get("modalidade_confirmada"),
        "evidencia_validacao": validated.get("evidencia_validacao"),
    }
    return _truncate(
        {
            "schema_version": structured.get("schema_version"),
            "startup_estado_atual": startup,
            "entrega1": {
                "gaps_identificados": delivery1.get("gaps_identificados", []),
                "recomendacoes_nvidia": delivery1.get(
                    "recomendacoes_nvidia", []
                ),
                "resposta_rag": delivery1.get("resposta_rag"),
            },
            "comparacao_competitiva": {
                "pesquisa": competitive.get("pesquisa"),
                "status_validacao": competitive.get("status_validacao"),
                "servico_bigtech_validado": compact_validated,
                "comparacao_estado_atual": competitive.get(
                    "comparacao_estado_atual"
                ),
            },
            "pricing": structured.get("pricing"),
            "alavancagem_nvidia": structured.get("alavancagem_nvidia"),
            "dados_insuficientes": structured.get(
                "dados_insuficientes", []
            ),
        },
        limit=400,
    )


def deterministic_competitive_briefing(state: AgentState) -> str:
    structured = state.get("structured_output") or {}
    startup = structured.get("startup_estado_atual") or {}
    delivery1 = structured.get("entrega1") or {}
    competitive = structured.get("comparacao_competitiva") or {}
    comparison = competitive.get("comparacao_estado_atual") or {}
    pricing = structured.get("pricing") or {}
    gaps = delivery1.get("gaps_identificados") or []
    recommendations = delivery1.get("recomendacoes_nvidia") or []
    lines = [
        f"## {startup.get('empresa') or 'Startup'} — análise competitiva",
        "",
        f"**Serviço atual:** {startup.get('servico_analisado') or 'não documentado'}",
        f"**GitHub Discovery:** {json.dumps(startup.get('github_discovery'), ensure_ascii=False, default=str)}",
        "",
        "### Entrega 1",
        f"**Gaps documentados:** {json.dumps(gaps, ensure_ascii=False, default=str)}",
        f"**Recomendações NVIDIA futuras:** {json.dumps(recommendations, ensure_ascii=False, default=str)}",
        "",
        "### Comparação do estado atual",
        f"**Status:** {competitive.get('status_validacao') or 'não disponível'}",
        f"**Quem entrega mais hoje:** {comparison.get('quem_entrega_mais_hoje') or 'não determinado'}",
        f"**Justificativa:** {comparison.get('justificativa') or 'dados insuficientes'}",
        "",
        "### Preço e alavancagem",
        f"**Preço:** {pricing.get('analise_custo_beneficio') or 'não disponível'}",
        f"**Alavancagem NVIDIA:** {json.dumps(structured.get('alavancagem_nvidia'), ensure_ascii=False, default=str)}",
        "",
        f"**Dados insuficientes:** {json.dumps(structured.get('dados_insuficientes', []), ensure_ascii=False, default=str)}",
    ]
    return "\n".join(lines)


def briefing_agent(state: AgentState) -> dict:
    client = Groq(api_key=required_env("GROQ_API_KEY"))
    model = os.getenv("GROQ_BRIEFING_MODEL", "qwen/qwen3-32b")
    competitive = state.get("output_mode") == "competitive" or bool(
        state.get("search_string_gerada")
    )
    if competitive:
        user_content = json.dumps(
            compact_competitive_payload(state),
            ensure_ascii=False,
            indent=2,
        )
    else:
        user_content = (
            f"Pergunta:\n{state['question']}\n\n"
            f"Resposta RAG:\n{state['rag_answer']}\n\n"
            f"Recomendacoes:\n{state['recommendation']}"
        )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        COMPETITIVE_BRIEFING_PROMPT
                        if competitive
                        else BRIEFING_PROMPT
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_completion_tokens=800 if competitive else 1600,
        )
        briefing = clean_briefing(response.choices[0].message.content)
    except Exception:
        if not competitive:
            raise
        briefing = deterministic_competitive_briefing(state)
    update = {"briefing": briefing, "final_answer": briefing}
    if competitive:
        update["competitive_report"] = briefing
    return update
