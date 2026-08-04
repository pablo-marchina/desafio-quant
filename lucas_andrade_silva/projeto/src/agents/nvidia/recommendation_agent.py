import os
import json
import re

from groq import Groq

from agents.nvidia.competitive.common import call_json
from agents.nvidia.state import AgentState
from rag.settings import required_env

RECOMMENDATION_PROMPT = """
Voce e um arquiteto de solucoes NVIDIA.
Produza recomendacoes somente com base nas evidencias recuperadas fornecidas.
Explique quais servicos atendem melhor ao objetivo da pergunta, os principais
trade-offs e os pontos que ainda precisam ser validados.
Cada afirmacao concreta e cada recomendacao devem citar [Fonte N].
Nao introduza produtos, modelos, GPUs, provedores, comandos, precos,
capacidades ou requisitos ausentes nas evidencias.
Nao crie procedimentos de implementacao ou provas de conceito.
Quando as evidencias nao sustentarem uma decisao, formule perguntas objetivas
na secao "Pontos a validar", sem preencher as lacunas.
Responda no idioma da pergunta.
""".strip()


def _citation_url_map(chunks: list[dict]) -> dict[str, str]:
    return {
        f"[Fonte {index}]": str(chunk.get("source_url") or "")
        for index, chunk in enumerate(chunks, start=1)
        if chunk.get("source_url")
    }


def _citations_from_sources(sources: list[object]) -> set[str]:
    return set(
        re.findall(
            r"\[Fonte \d+\]",
            " ".join(source for source in sources if isinstance(source, str)),
        )
    )


def _replace_citations_with_urls(
    recommendations: list[dict], citation_urls: dict[str, str]
) -> list[dict]:
    converted = []
    for item in recommendations:
        citations = _citations_from_sources(item.get("fontes") or [])
        urls = [
            citation_urls[citation]
            for citation in citations
            if citation_urls.get(citation)
        ]
        converted.append({**item, "fontes": list(dict.fromkeys(urls))})
    return converted


def recommendation_agent(state: AgentState) -> dict:
    from rag.generation.rag_query import build_context

    startup_analysis = bool(state.get("startup_mencionada") or state.get("empresa"))
    if startup_analysis:
        gaps = [
            gap
            for gap in state.get("gaps_identificados", [])
            if isinstance(gap, dict) and gap.get("gap")
        ]
        if not gaps:
            service_description = str(
                state.get("servico_startup_analisado")
                or state.get("dor_resolvida")
                or ""
            ).strip()
            if not service_description:
                structured = {
                    "recomendacoes_nvidia": [],
                    "tradeoffs": [],
                    "pontos_a_validar": [
                        "Documentar o serviço atual da startup ou informar "
                        "um gap antes de recomendar um produto NVIDIA."
                    ],
                    "status": "dados_insuficientes",
                    "base_recomendacao": "nenhuma",
                }
            else:
                structured = call_json(
                    """
Você é um arquiteto de soluções NVIDIA. Não há gap atual documentado.
Identifique 3 recomendações NVIDIA com maior aderência funcional ao serviço
que a startup já oferece quando houver evidências suficientes; se houver menos
evidências, retorne apenas as recomendações sustentadas. Isso é uma oportunidade de fit,
não a correção de uma deficiência comprovada.

Combine, quando as evidências sustentarem, programas/ecossistema NVIDIA e
serviços NVIDIA específicos. Use somente produtos, programas e capacidades
presentes nas evidências RAG. Cada item
precisa citar ao menos uma [Fonte N]. Se não houver correspondência funcional
sustentada, retorne lista vazia. Retorne json:
{"recomendacoes_nvidia":[{"produto":"...","justificativa":"...",
"fontes":["[Fonte N]"]}],"tradeoffs":["..."],"pontos_a_validar":["..."],
"roadmap":["..."],"comparacao_bigtechs":["..."],
"status":"ok|dados_insuficientes"}.
""".strip(),
                    {
                        "empresa": state.get("empresa"),
                        "servico_atual_documentado": service_description,
                        "resposta_rag": state["rag_answer"],
                        "evidencias_rag": build_context(
                            state["retrieved_chunks"]
                        ),
                    },
                )
                allowed_citations = {
                    f"[Fonte {index}]"
                    for index in range(
                        1, len(state["retrieved_chunks"]) + 1
                    )
                }
                citation_urls = _citation_url_map(state["retrieved_chunks"])
                recommendations = []
                for item in structured.get("recomendacoes_nvidia", []):
                    if (
                        not isinstance(item, dict)
                        or not item.get("produto")
                        or not item.get("justificativa")
                        or not isinstance(item.get("fontes"), list)
                    ):
                        continue
                    citations = _citations_from_sources(item["fontes"])
                    if (
                        not citations
                        or not citations <= allowed_citations
                    ):
                        continue
                    recommendations.append(
                        {
                            **item,
                            "gap": (
                                "Aderência funcional ao serviço atual "
                                "(nenhum gap documentado)"
                            ),
                            "base_recomendacao": "aderencia_funcional",
                        }
                    )
                structured["recomendacoes_nvidia"] = _replace_citations_with_urls(
                    recommendations[:3], citation_urls
                )
                structured["base_recomendacao"] = "aderencia_funcional"
                structured["aviso"] = (
                    "Recomendação por aderência funcional; não representa "
                    "um gap comprovado da startup."
                )
                if not structured["recomendacoes_nvidia"]:
                    structured["status"] = "dados_insuficientes"
            recommendation = json.dumps(
                structured, ensure_ascii=False, indent=2
            )
            update = {
                "recommendation": recommendation,
                "recomendacoes_nvidia": structured[
                    "recomendacoes_nvidia"
                ],
                "structured_output": structured,
            }
            if state.get("output_mode") == "recommendation":
                update["final_answer"] = recommendation
            return update

        structured = call_json(
            """
Você é um arquiteto de soluções NVIDIA. Recomende somente produtos sustentados
pelas evidências RAG e somente para os gaps documentados fornecidos. Cada item
deve repetir literalmente o campo gap recebido. Não use segmento, setor ou
descrição geral como substituto de gap. Não crie capacidades nem produtos.
Retorne 3 recomendações quando houver evidências suficientes; se houver menos
evidências, retorne apenas as recomendações sustentadas. Inclua roadmap
resumido e comparação com big techs somente em pontos sustentados ou como
validações pendentes.
Retorne json:
{"recomendacoes_nvidia":[{"gap":"...","produto":"...",
"justificativa":"...","fontes":["[Fonte N]"]}],
"tradeoffs":["..."],"pontos_a_validar":["..."],"roadmap":["..."],
"comparacao_bigtechs":["..."],"status":"ok|dados_insuficientes"}.
""".strip(),
            {
                "pergunta": state.get("original_question") or state["question"],
                "gaps_documentados": gaps,
                "resposta_rag": state["rag_answer"],
                "evidencias_rag": build_context(state["retrieved_chunks"]),
            },
        )
        allowed_gaps = {str(gap["gap"]) for gap in gaps}
        allowed_citations = {
            f"[Fonte {index}]"
            for index in range(1, len(state["retrieved_chunks"]) + 1)
        }
        citation_urls = _citation_url_map(state["retrieved_chunks"])
        recommendations = []
        for item in structured.get("recomendacoes_nvidia", []):
            if (
                not isinstance(item, dict)
                or str(item.get("gap") or "") not in allowed_gaps
                or not item.get("produto")
                or not isinstance(item.get("fontes"), list)
                or not item["fontes"]
                or not all(
                    isinstance(source, str) for source in item["fontes"]
                )
            ):
                continue
            citations = _citations_from_sources(item["fontes"])
            if not citations or not citations <= allowed_citations:
                continue
            recommendations.append(item)
        structured["recomendacoes_nvidia"] = _replace_citations_with_urls(
            recommendations[:3], citation_urls
        )
        if not recommendations:
            structured["status"] = "dados_insuficientes"
        recommendation = json.dumps(structured, ensure_ascii=False, indent=2)
        update = {
            "recommendation": recommendation,
            "recomendacoes_nvidia": structured["recomendacoes_nvidia"],
            "structured_output": structured,
        }
        if state.get("output_mode") == "recommendation":
            update["final_answer"] = recommendation
        return update

    client = Groq(api_key=required_env("GROQ_API_KEY"))
    model = os.getenv("GROQ_RECOMMENDATION_MODEL", "llama-3.3-70b-versatile")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": RECOMMENDATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Pergunta:\n{state['question']}\n\n"
                    f"Resposta RAG:\n{state['rag_answer']}\n\n"
                    "Evidencias recuperadas:\n"
                    f"{build_context(state['retrieved_chunks'])}"
                ),
            },
        ],
        temperature=0.2,
        max_completion_tokens=1400,
    )
    recommendation = response.choices[0].message.content
    update = {"recommendation": recommendation}
    if state.get("output_mode", "briefing") == "recommendation":
        update["final_answer"] = recommendation
    return update
