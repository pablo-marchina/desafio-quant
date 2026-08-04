import json
from datetime import datetime, timezone
import json
from pipeline.db.connection import execute_query, fetch_one


def _gerar_markdown(briefing: dict) -> str:
    s = briefing.get("startup", {})
    p = briefing.get("perfil_ia", {})
    evs = briefing.get("evidencias_chave", [])
    recs = briefing.get("recomendacoes_nvidia", [])
    gaps = briefing.get("gaps_tecnicos", [])

    md = f"""# Briefing: {s.get('nome', 'N/A')}

## Dados da Startup
- **Website:** {s.get('website', 'N/A')}
- **Setor:** {s.get('setor', 'N/A')}
- **Cidade:** {s.get('cidade', 'N/A')}
- **Estágio:** {s.get('estagio', 'N/A')}
- **Descrição:** {s.get('descricao', 'N/A')}

## Perfil de IA
- **Classificação:** {p.get('classificacao', 'N/A')}
- **Ramo:** {p.get('ramo', 'N/A')}
- **Score de Fit NVIDIA:** {p.get('score_fit_nvidia', 'N/A')}/100

## Gaps Técnicos Identificados
"""
    for g in gaps:
        md += f"- {g}\n"

    md += "\n## Evidências Coletadas\n"
    for ev in evs[:5]:
        md += f"- [{ev.get('tipo', 'N/A')}] {ev.get('titulo', '')} - {ev.get('url', '')} (score: {ev.get('score', 0)})\n"

    md += "\n## Recomendações NVIDIA\n"
    for r in recs:
        md += f"""### {r.get('rank', '#')}. {r.get('tecnologia', 'N/A')}
- **Categoria:** {r.get('categoria', 'N/A')}
- **Prioridade:** {r.get('nivel_prioridade', 'N/A')}
- **Complexidade:** {r.get('complexidade_implementacao', 'N/A')}
- **Justificativa Técnica:** {r.get('justificativa_tecnica', 'N/A')}
- **Justificativa de Negócio:** {r.get('justificativa_negocio', 'N/A')}
- **Próxima Ação:** {r.get('proxima_acao_sugerida', 'N/A')}
- **Referência:** {r.get('url_referencia', 'N/A')}

"""

    md += f"""## Resumo Executivo
{briefing.get('resumo_executivo', '')}

---
Gerado em: {briefing.get('gerado_em', '')}
"""
    return md


def _buscar_dados_combinados(startup_id: str) -> dict | None:
    from pipeline.db.connection import fetch_all

    startup = fetch_one("SELECT * FROM startups WHERE id = ?", (startup_id,))
    if not startup:
        return None

    classificacao = fetch_one(
        "SELECT * FROM classificacoes WHERE startup_id = ? ORDER BY classificado_em DESC LIMIT 1",
        (startup_id,)
    )
    evidencias = fetch_all(
        "SELECT * FROM evidencias WHERE startup_id = ? ORDER BY score_qualidade DESC LIMIT 5",
        (startup_id,)
    )
    recomendacoes = None  # será passado do estado

    if classificacao and isinstance(classificacao.get("gaps_identificados"), str):
        classificacao["gaps_identificados"] = json.loads(classificacao["gaps_identificados"])

    return {
        "startup": startup,
        "classificacao": classificacao,
        "evidencias": evidencias,
        "recomendacoes": recomendacoes
    }


def run_briefing_agent(recomendacoes_finais: list[dict]) -> list[dict]:
    briefings = []

    for item in recomendacoes_finais:
        nome = item.get("startup_nome", "desconhecida")
        startup_id = item.get("startup_id")
        print(f"[Briefing] Gerando briefing para: {nome}")

        dados = _buscar_dados_combinados(startup_id) if startup_id else None

        recs_nvidia = []
        for r in item.get("recomendacoes", []):
            recs_nvidia.append({
                "rank": r.get("rank"),
                "tecnologia": r.get("tecnologia"),
                "categoria": r.get("categoria"),
                "justificativa_tecnica": r.get("justificativa_tecnica"),
                "justificativa_negocio": r.get("justificativa_negocio"),
                "nivel_prioridade": r.get("nivel_prioridade"),
                "complexidade_implementacao": r.get("complexidade_implementacao"),
                "melhor_encaixe": r.get("melhor_encaixe"),
                "proxima_acao_sugerida": r.get("proxima_acao_sugerida"),
                "evidencias_usadas": r.get("evidencias_usadas", []),
                "url_referencia": r.get("url_referencia")
            })

        resumo = f"Startup {nome} classificada como AI-native no setor, com score de fit NVIDIA calculado. "
        if recs_nvidia:
            top = recs_nvidia[0]
            resumo += f"Recomendação prioritária: {top['tecnologia']} ({top['nivel_prioridade']}). {top['proxima_acao_sugerida']}"

        agora = datetime.now(timezone.utc).isoformat()

        briefing_json = {
            "startup": {
                "nome": dados["startup"]["nome"] if dados else nome,
                "website": dados["startup"]["website"] if dados else None,
                "setor": dados["startup"]["setor"] if dados else None,
                "descricao": dados["startup"]["descricao"] if dados else None,
                "produto_principal": dados["startup"]["produto_principal"] if dados else None,
                "estagio": dados["startup"]["estagio"] if dados else None,
                "cidade": dados["startup"]["cidade"] if dados else None,
                "pais": "Brasil"
            },
            "perfil_ia": {
                "classificacao": dados["classificacao"]["ai_classification"] if dados and dados.get("classificacao") else "ai-native",
                "ramo": dados["classificacao"]["ramo_principal"] if dados and dados.get("classificacao") else None,
                "score_fit_nvidia": dados["classificacao"]["score_fit_nvidia"] if dados and dados.get("classificacao") else None
            },
            "evidencias_chave": [
                {
                    "tipo": ev.get("tipo", "site"),
                    "url": ev.get("url", ""),
                    "titulo": ev.get("titulo", ""),
                    "data": ev.get("data_publicacao"),
                    "score": ev.get("score_qualidade", 0)
                }
                for ev in (dados["evidencias"] if dados and dados.get("evidencias") else [])
            ] if dados and dados.get("evidencias") else [],
            "gaps_tecnicos": dados["classificacao"]["gaps_identificados"] if dados and dados.get("classificacao") else [],
            "recomendacoes_nvidia": recs_nvidia,
            "resumo_executivo": resumo,
            "proxima_acao_sugerida": recs_nvidia[0]["proxima_acao_sugerida"] if recs_nvidia else "Aguardando dados para gerar ação",
            "gerado_em": agora
        }

        briefing_markdown = _gerar_markdown(briefing_json)

        if startup_id:
            execute_query(
                """INSERT INTO briefings (startup_id, conteudo_json, conteudo_markdown)
                VALUES (?, ?, ?)""",
                (startup_id, json.dumps(briefing_json, ensure_ascii=False), briefing_markdown)
            )

        briefings.append(briefing_json)

    print(f"[Briefing] {len(briefings)} briefings gerados")
    return briefings
