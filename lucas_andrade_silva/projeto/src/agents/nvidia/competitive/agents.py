from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from agents.nvidia.state import AgentState

from .common import call_json
from .search import (
    OFFICIAL_DOMAINS,
    scrape_official_candidate,
    search_official_candidates,
    search_pricing_page,
)

MAX_BIGTECH_ATTEMPTS = 6

BIGTECH_REFERENCE_COMPANIES = list(OFFICIAL_DOMAINS)


def search_string_generator_agent(state: AgentState) -> dict[str, Any]:
    result = call_json(
        """
Transforme o serviço da startup numa busca neutra por categoria de produto.
Não cite nem pressuponha provedores. Combine tarefa central e modalidade de
entrega (API, SaaS, ferramenta de desenvolvedor etc.). Gere de 3 a 5 buscas em
inglês, da descrição mais específica até a função central mais ampla, para
localizar páginas globais. Selecione de 8 a 12 empresas com maior probabilidade
de possuir um produto equivalente. Considere tanto empresas de
tecnologia quanto grandes empresas dos setores financeiro, industrial, saúde,
varejo e logística, usando somente nomes da lista fornecida. Retorne somente JSON:
{"search_string_gerada":"...", "categoria_funcional":"...",
"search_strings_geradas":["..."],"empresas_candidatas":["..."]}.
""".strip(),
        {
            "servico_startup_analisado": state["servico_startup_analisado"],
            "empresas_referencia": BIGTECH_REFERENCE_COMPANIES,
        },
    )
    company_names = {
        company.casefold(): company for company in BIGTECH_REFERENCE_COMPANIES
    }
    candidate_companies = []
    for value in result.get("empresas_candidatas", []):
        company = company_names.get(str(value).strip().casefold())
        if company and company not in candidate_companies:
            candidate_companies.append(company)
    primary_search = str(result["search_string_gerada"]).strip()
    search_strings = []
    for value in [primary_search, *result.get("search_strings_geradas", [])]:
        search_string = str(value).strip()
        if search_string and search_string.casefold() not in {
            item.casefold() for item in search_strings
        }:
            search_strings.append(search_string)
    return {
        "search_string_gerada": primary_search,
        "search_strings_geradas": search_strings[:5],
        "categoria_funcional": str(result["categoria_funcional"]).strip(),
        "bigtech_empresas_candidatas": candidate_companies[:12],
        "bigtech_candidatos_testados": [],
        "bigtech_tentativas": 0,
        "bigtech_validacao_status": "pendente",
        "dados_insuficientes": list(state.get("dados_insuficientes", [])),
    }


def bigtech_scraper_agent(state: AgentState) -> dict[str, Any]:
    attempts = int(state.get("bigtech_tentativas", 0))
    tested = list(state.get("bigtech_candidatos_testados", []))
    insufficient = list(state.get("dados_insuficientes", []))
    if attempts >= MAX_BIGTECH_ATTEMPTS:
        insufficient.append(
            f"Nenhum serviço equivalente confirmado após "
            f"{MAX_BIGTECH_ATTEMPTS} tentativas."
        )
        return {
            "bigtech_validacao_status": "esgotado",
            "bigtech_servico_validado": None,
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
        }
    try:
        candidates = search_official_candidates(
            state.get("search_strings_geradas")
            or state["search_string_gerada"],
            set(tested),
            state.get("bigtech_empresas_candidatas") or None,
        )
        if not candidates:
            insufficient.append("Busca não encontrou outra página oficial candidata.")
            return {
                "bigtech_tentativas": attempts + 1,
                "bigtech_validacao_status": "esgotado",
                "bigtech_servico_validado": None,
                "dados_insuficientes": list(dict.fromkeys(insufficient)),
            }
        candidate = candidates[0]
        tested.append(candidate["url"])
        scraped = scrape_official_candidate(candidate)
        return {
            "bigtech_candidato": scraped,
            "bigtech_candidatos_testados": tested,
            "bigtech_tentativas": attempts + 1,
            "bigtech_validacao_status": "pendente",
        }
    except Exception as error:
        insufficient.append(f"Falha na busca oficial: {error}")
        status = "esgotado" if attempts + 1 >= MAX_BIGTECH_ATTEMPTS else "rejeitado"
        return {
            "bigtech_tentativas": attempts + 1,
            "bigtech_validacao_status": status,
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
        }


def equivalence_validator_agent(state: AgentState) -> dict[str, Any]:
    candidate = state.get("bigtech_candidato")
    if not candidate:
        return {"bigtech_validacao_status": "rejeitado"}
    result = call_json(
        """
Valide equivalência direta. validado=true SOMENTE se (1) a tarefa central for
da mesma categoria funcional e (2) a modalidade de entrega for comparável.
Proximidade temática não basta. Use apenas a evidência fornecida. Retorne
{"validado":bool,"categoria_funcional_confirmada":"...","modalidade_confirmada":"...",
"evidencia":"..."} ou {"validado":false,"motivo":"..."}.
""".strip(),
        {
            "servico_startup": state["servico_startup_analisado"],
            "categoria_esperada": state["categoria_funcional"],
            "candidato": candidate,
        },
    )
    if result.get("validado") is not True:
        insufficient = list(state.get("dados_insuficientes", []))
        insufficient.append(
            f"Candidato {candidate['candidato_url']} rejeitado: "
            f"{result.get('motivo', 'critérios de equivalência não atendidos')}"
        )
        status = (
            "esgotado"
            if int(state.get("bigtech_tentativas", 0)) >= MAX_BIGTECH_ATTEMPTS
            else "rejeitado"
        )
        return {
            "bigtech_validacao_status": status,
            "bigtech_servico_validado": None,
            "dados_insuficientes": insufficient,
        }
    validated = {
        **candidate,
        "categoria_funcional_confirmada": result.get(
            "categoria_funcional_confirmada"
        ),
        "modalidade_confirmada": result.get("modalidade_confirmada"),
        "evidencia_validacao": result.get("evidencia"),
    }
    return {
        "bigtech_validacao_status": "confirmado",
        "bigtech_servico_validado": validated,
    }


def comparison_agent(state: AgentState) -> dict[str, Any]:
    result = call_json(
        """
Compare EXCLUSIVAMENTE o estado atual documentado da startup com o serviço
equivalente atual da big tech. A recomendação NVIDIA é futura e está fora do
escopo: não cite, some ou atribua produtos NVIDIA à startup. Todo ponto deve ter
aspecto, evidencia e fonte. Omita aspectos sem fonte. Não presuma qualidade,
escala ou suporte. O campo evidencia deve copiar um trecho literal das
evidências de entrada.
Retorne {"pontos_fortes_startup":[...],"pontos_fracos_startup":[...],
"pontos_fortes_bigtech":[...],"pontos_fracos_bigtech":[...],
"quem_entrega_mais_hoje":"startup|bigtech|equivalente","justificativa":"..."}.
""".strip(),
        {
            "estado_atual_startup": {
                "empresa": state.get("empresa"),
                "servico": state["servico_startup_analisado"],
                "evidencias": state.get("pontos_fortes", []),
                "fonte_oficial": state.get("startup_url"),
            },
            "servico_bigtech_atual_validado": state[
                "bigtech_servico_validado"
            ],
            "fora_do_escopo": [
                "recomendacao NVIDIA",
                "produto NVIDIA futuro",
                "arquitetura ainda nao implementada",
            ],
        },
    )
    allowed_sources = {str(state.get("startup_url") or "")}
    startup_url = str(state.get("startup_url") or "")
    bigtech_url = str(
        state["bigtech_servico_validado"].get("candidato_url") or ""
    )
    allowed_sources.add(bigtech_url)
    source_evidence: dict[str, str] = {
        startup_url: str(state.get("servico_startup_analisado") or "")
    }
    bigtech_content = state["bigtech_servico_validado"].get(
        "candidato_conteudo", {}
    )
    source_evidence[bigtech_url] = " ".join(
        str(bigtech_content.get(key) or "")
        for key in (
            "titulo_produto",
            "descricao_oficial",
            "trecho_relevante",
        )
    )
    for point in state.get("pontos_fortes", []):
        if isinstance(point, dict):
            source = str(point.get("fonte") or "")
            allowed_sources.add(source)
            source_evidence[source] = (
                source_evidence.get(source, "")
                + " "
                + str(point.get("evidencia") or "")
            )
    allowed_sources.discard("")
    point_keys = (
        "pontos_fortes_startup",
        "pontos_fracos_startup",
        "pontos_fortes_bigtech",
        "pontos_fracos_bigtech",
    )
    current_startup_text = " ".join(
        [
            str(state.get("servico_startup_analisado") or ""),
            *[
                f"{point.get('aspecto', '')} {point.get('evidencia', '')}"
                for point in state.get("pontos_fortes", [])
                if isinstance(point, dict)
            ],
        ]
    ).casefold()
    for key in point_keys:
        points = result.get(key)
        if not isinstance(points, list):
            result[key] = []
            continue
        filtered = []
        for point in points:
            if (
                not isinstance(point, dict)
                or str(point.get("fonte") or "") not in allowed_sources
                or not point.get("evidencia")
                or str(point.get("evidencia") or "").casefold()
                not in source_evidence.get(
                    str(point.get("fonte") or ""), ""
                ).casefold()
            ):
                continue
            point_text = (
                f"{point.get('aspecto', '')} {point.get('evidencia', '')}"
            ).casefold()
            if (
                key.endswith("_startup")
                and "nvidia" in point_text
                and "nvidia" not in current_startup_text
            ):
                continue
            filtered.append(point)
        result[key] = filtered
    result["escopo_comparacao"] = (
        "estado_atual_startup_vs_servico_bigtech_atual_validado"
    )
    result["lado_startup"] = f"{state.get('empresa') or 'startup'} (estado atual)"
    result["lado_bigtech"] = (
        f"{state['bigtech_servico_validado'].get('candidato_empresa') or 'big tech'} "
        "(serviço atual validado)"
    )
    if not any(result[key] for key in point_keys):
        result["quem_entrega_mais_hoje"] = "equivalente"
        result["justificativa"] = (
            "Dados documentais insuficientes para determinar uma vantagem."
        )
    winner = result.get("quem_entrega_mais_hoje")
    if winner == "startup" and not (
        result["pontos_fortes_startup"] or result["pontos_fracos_bigtech"]
    ):
        result["quem_entrega_mais_hoje"] = "equivalente"
        result["justificativa"] = "A vantagem da startup não possui evidência válida."
    if winner == "bigtech" and not (
        result["pontos_fortes_bigtech"] or result["pontos_fracos_startup"]
    ):
        result["quem_entrega_mais_hoje"] = "equivalente"
        result["justificativa"] = "A vantagem da big tech não possui evidência válida."
    return {"comparacao_pontos_fortes_fracos": result}


def bigtech_axis_summary_agent(state: AgentState) -> dict[str, Any]:
    validated = state.get("bigtech_servico_validado")
    if not validated:
        return {
            "comparacao_bigtechs_resumida": _no_direct_equivalent_summary(state)
        }
    result = call_json(
        """
Compare a startup com big techs usando este raciocínio:
1. Traduza descrição + CNAE da startup em uma categoria funcional genérica:
o que ela faz tecnicamente, não como se vende.
2. Identifique produtos/serviços equivalentes nas empresas de referência
fornecidas. Use o serviço validado como evidência forte. Inclua outros
equivalentes somente quando houver alta confiança funcional; se não tiver
certeza, declare isso no campo como_resolve. Não force comparação para função
muito nichada/local.
3. Compare em três eixos: onde big tech vence, onde startup vence e risco de
substituição no médio prazo.
Retorne exatamente este JSON:
{"categoria_funcional":"...","equivalentes_big_tech":[{"empresa":"...",
"produto":"...","como_resolve":"..."}],"vantagem_bigtech":"...",
"vantagem_startup":"...","risco_substituicao":"Alto|Médio|Baixo + justificativa"}.
Se a função for muito nichada/local, use categoria_funcional começando com
"sem equivalente direto relevante em big tech" e explique a vantagem estrutural
por especialização.
""".strip(),
        {
            "startup": {
                "empresa": state.get("empresa"),
                "descricao": state.get("servico_startup_analisado"),
                "cnae": state.get("cnae"),
                "url": state.get("startup_url"),
            },
            "categoria_funcional_previa": state.get("categoria_funcional"),
            "servico_bigtech_validado": validated,
            "comparacao_documental": state.get("comparacao_pontos_fortes_fracos"),
            "empresas_referencia": BIGTECH_REFERENCE_COMPANIES,
            "regra": (
                "nao force uma comparacao se a funcao da startup for muito "
                "nichada/local; declare sem equivalente direto relevante"
            ),
        },
    )
    equivalents = result.get("equivalentes_big_tech")
    if not isinstance(equivalents, list):
        equivalents = []
    normalized_equivalents = []
    for item in equivalents:
        if not isinstance(item, dict):
            continue
        company = str(item.get("empresa") or "").strip()
        product = str(item.get("produto") or "").strip()
        how = str(item.get("como_resolve") or "").strip()
        if company and product and how:
            normalized_equivalents.append(
                {"empresa": company, "produto": product, "como_resolve": how}
            )
    if not normalized_equivalents:
        content = validated.get("candidato_conteudo", {}) or {}
        normalized_equivalents = [
            {
                "empresa": str(validated.get("candidato_empresa") or "Big tech"),
                "produto": str(
                    content.get("titulo_produto")
                    or validated.get("candidato_titulo")
                    or "serviço validado"
                ),
                "como_resolve": str(
                    validated.get("evidencia_validacao")
                    or content.get("trecho_relevante")
                    or "Equivalência funcional validada pelas evidências oficiais."
                ),
            }
        ]
    risk = str(result.get("risco_substituicao") or "").strip()
    if not risk.startswith(("Alto", "Médio", "Baixo")):
        risk = f"Médio - {risk or 'há equivalência funcional parcial, mas a comparação depende do grau de nicho e integração local.'}"
    summary = {
        "categoria_funcional": str(
            result.get("categoria_funcional") or state.get("categoria_funcional") or ""
        ).strip(),
        "equivalentes_big_tech": normalized_equivalents,
        "vantagem_bigtech": str(result.get("vantagem_bigtech") or "").strip(),
        "vantagem_startup": str(result.get("vantagem_startup") or "").strip(),
        "risco_substituicao": risk,
    }
    return {"comparacao_bigtechs_resumida": summary}


def _no_direct_equivalent_summary(state: AgentState) -> dict[str, Any]:
    category = str(state.get("categoria_funcional") or "").strip()
    suffix = f": {category}" if category else ""
    return {
        "categoria_funcional": (
            "sem equivalente direto relevante em big tech, vantagem estrutural "
            f"por especialização{suffix}"
        ),
        "equivalentes_big_tech": [],
        "vantagem_bigtech": (
            "Sem equivalente direto validado nas fontes oficiais consultadas; "
            "big techs ainda podem vencer em escala, infraestrutura global e "
            "preço por volume quando a função for padronizável."
        ),
        "vantagem_startup": (
            "Especialização no setor, customização, suporte local e agilidade "
            "para adaptar o produto ao contexto do cliente."
        ),
        "risco_substituicao": (
            "Baixo - nenhum equivalente direto relevante foi confirmado; o "
            "risco aumenta apenas se a solução puder ser reduzida a uma "
            "categoria genérica de plataforma."
        ),
    }


def _official_startup_host(state: AgentState) -> str | None:
    url = str(state.get("startup_url") or "")
    return (urlsplit(url).hostname or "").casefold().removeprefix("www.") or None


def pricing_agent(state: AgentState) -> dict[str, Any]:
    startup_host = _official_startup_host(state)
    validated = state["bigtech_servico_validado"]
    company = str(validated.get("candidato_empresa") or "")
    title = str(
        validated.get("candidato_conteudo", {}).get("titulo_produto") or ""
    )
    startup_evidence = search_pricing_page(
        f"{state.get('empresa', '')} {state['servico_startup_analisado']}",
        (startup_host,) if startup_host else (),
    )
    bigtech_evidence = search_pricing_page(
        f"{company} {title}",
        OFFICIAL_DOMAINS.get(company, ()),
    )
    result = call_json(
        """
Identifique preço SOMENTE se a evidência veio de uma página oficial de pricing.
Não estime. "Fale com vendas" é nao_disponivel. Se qualquer preço faltar, a
analise_custo_beneficio deve ser exatamente "comparação de preço não disponível".
Retorne {"preco_startup":{"valor":"...|nao_disponivel","fonte_url":null|"https://..."},
"preco_bigtech":{"valor":"...|nao_disponivel","fonte_url":null|"https://..."},
"analise_custo_beneficio":"..."}.
""".strip(),
        {
            "startup": {
                "host_oficial": startup_host,
                "servico": state["servico_startup_analisado"],
                "pagina_pricing": startup_evidence,
            },
            "bigtech": {
                "servico": validated,
                "pagina_pricing": bigtech_evidence,
            },
        },
    )
    startup = result.get("preco_startup") or {}
    bigtech = result.get("preco_bigtech") or {}
    for price, evidence in (
        (startup, startup_evidence),
        (bigtech, bigtech_evidence),
    ):
        evidence_url = evidence.get("url") if evidence else None
        if (
            price.get("valor") != "nao_disponivel"
            and price.get("fonte_url") != evidence_url
        ):
            price.update({"valor": "nao_disponivel", "fonte_url": None})
    analysis = result.get("analise_custo_beneficio", "")
    if (
        startup.get("valor") == "nao_disponivel"
        or bigtech.get("valor") == "nao_disponivel"
    ):
        analysis = "comparação de preço não disponível"
    return {
        "preco_startup": startup,
        "preco_bigtech": bigtech,
        "analise_custo_beneficio": analysis,
    }


def leverage_agent(state: AgentState) -> dict[str, Any]:
    comparison = state["comparacao_pontos_fortes_fracos"]
    documented_gaps = [
        gap
        for gap in state.get("gaps_identificados", [])
        if isinstance(gap, dict)
        and str(gap.get("gap") or "").strip()
        and gap.get("evidencia")
        and gap.get("fonte")
    ]
    if not documented_gaps:
        insufficient = list(state.get("dados_insuficientes", []))
        insufficient.append(
            "Leverage não executado: nenhum gap explícito e documentado veio "
            "da Entrega 1."
        )
        return {
            "alavancagem_nvidia": None,
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
        }
    recommendations = [
        item
        for item in state.get("recomendacoes_nvidia", [])
        if isinstance(item, dict) and item.get("produto") and item.get("gap")
    ]
    if not recommendations:
        insufficient = list(state.get("dados_insuficientes", []))
        insufficient.append(
            "Leverage não executado: não existe recomendação NVIDIA estruturada "
            "e vinculada a um gap documentado."
        )
        return {
            "alavancagem_nvidia": None,
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
        }
    result = call_json(
        """
Escolha somente um produto NVIDIA já presente nas recomendações estruturadas.
Vincule-o literalmente a um gap documentado da Entrega 1. Não crie gap, não
use apenas um ponto forte da big tech e não sugira produto novo.
Mapeie startup->na_frente, bigtech->atras, equivalente->equivalente. Retorne
{"situacao_atual":"atras|na_frente|equivalente","produto_nvidia_chave":"...",
"como_fecha_a_lacuna_ou_aumenta_vantagem":"...",
"gap_referenciado":"...","conexao_com_gap_entrega1":"..."}.
""".strip(),
        {
            "comparacao": comparison,
            "gaps_entrega1": documented_gaps,
            "recomendacoes_nvidia_entrega1": recommendations,
        },
    )
    allowed_gap_names = {str(gap["gap"]) for gap in documented_gaps}
    allowed_pairs = {
        (str(item["gap"]), str(item["produto"])) for item in recommendations
    }
    selected_pair = (
        str(result.get("gap_referenciado") or ""),
        str(result.get("produto_nvidia_chave") or ""),
    )
    if (
        selected_pair not in allowed_pairs
        or selected_pair[0] not in allowed_gap_names
    ):
        insufficient = list(state.get("dados_insuficientes", []))
        insufficient.append(
            "A alavancagem não correspondeu literalmente a um par gap/produto "
            "documentado e foi descartada."
        )
        return {
            "alavancagem_nvidia": None,
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
        }
    return {"alavancagem_nvidia": result}


def competitive_synthesis_agent(state: AgentState) -> dict[str, Any]:
    """Consolidação determinística; preserva os contratos JSON dos agentes."""
    structured = {
        "schema_version": "competitive-analysis/v1",
        "startup_estado_atual": {
            "empresa": state.get("empresa"),
            "servico_analisado": state.get("servico_startup_analisado"),
            "cnae": state.get("cnae"),
            "stack_atual": state.get("stack_atual", []),
            "fontes": [
                point
                for point in state.get("pontos_fortes", [])
                if isinstance(point, dict)
            ],
            "github_discovery": state.get("github_discovery"),
        },
        "entrega1": {
            "gaps_identificados": state.get("gaps_identificados", []),
            "recomendacoes_nvidia": state.get("recomendacoes_nvidia", []),
            "resposta_rag": state.get("rag_answer"),
        },
        "comparacao_competitiva": {
            "pesquisa": {
                "search_string": state.get("search_string_gerada"),
                "empresas_candidatas": state.get(
                    "bigtech_empresas_candidatas", []
                ),
                "candidatos_testados": state.get(
                    "bigtech_candidatos_testados", []
                ),
                "tentativas": state.get("bigtech_tentativas", 0),
            },
            "status_validacao": state.get("bigtech_validacao_status"),
            "servico_bigtech_validado": state.get("bigtech_servico_validado"),
            "comparacao_estado_atual": state.get(
                "comparacao_pontos_fortes_fracos"
            ),
            "comparacao_bigtechs_resumida": state.get(
                "comparacao_bigtechs_resumida"
            )
            or _no_direct_equivalent_summary(state),
        },
        "pricing": {
            "startup": state.get("preco_startup"),
            "bigtech": state.get("preco_bigtech"),
            "analise_custo_beneficio": state.get(
                "analise_custo_beneficio"
            ),
        },
        "alavancagem_nvidia": state.get("alavancagem_nvidia"),
        "dados_insuficientes": list(
            dict.fromkeys(state.get("dados_insuficientes", []))
        ),
    }
    return {"structured_output": structured}
