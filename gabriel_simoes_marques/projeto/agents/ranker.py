"""
Ranker agent: recebe lista de StartupScores e produz ranking estratégico
para o time NVIDIA Inception Brasil.

Além de ordenar por score, o LLM gera:
- highlight por startup (por que está nessa posição)
- ação concreta por startup
- narrativa do portfólio completo
- quick wins vs long bets
"""

from models.score import StartupScore
from models.ranking import RankedStartup, RankingReport
from config.llm import chat_json, DEFAULT_MODEL


def _score_summary(s: StartupScore) -> str:
    return (
        f"{s.startup_name}: total={s.total} tier={s.tier} | "
        f"tech_fit={s.technical_fit.score} ai_maturity={s.ai_maturity.score} "
        f"market={s.market_potential.score} strategic={s.strategic_value.score} urgency={s.urgency.score}"
    )


async def rank_startups(scores: list[StartupScore], model: str = DEFAULT_MODEL) -> RankingReport:
    sorted_scores = sorted(scores, key=lambda s: s.total, reverse=True)

    scores_text = "\n".join(_score_summary(s) for s in sorted_scores)

    data = await chat_json(
        messages=[
            {
                "role": "system",
                "content": """Você é o diretor de parcerias NVIDIA Inception Brasil montando o ranking de startups para priorização do time de BD.

Para cada startup, escreva:
- highlight: 1 frase explicando por que está nessa posição (ex: "Stack GPU-ready + produto de inferência em escala")
- action: próximo passo concreto (ex: "Agendar demo NIM com CTO esta semana")

Depois analise o portfólio como um todo:
- strategic_summary: 2-3 frases sobre o portfólio — oportunidades, gaps, tendências
- top_pick: nome da startup mais recomendada para Inception imediato e por quê (1 frase)
- quick_wins: startups com alta urgência (urgency >= 7) e score >= 65 — lista de nomes
- long_bets: startups com alto potencial técnico mas early stage (urgency <= 5) — lista de nomes

Retorne JSON:
{
  "rankings": [
    {"startup_name": "X", "highlight": "...", "action": "..."},
    ...
  ],
  "strategic_summary": "...",
  "top_pick": "...",
  "quick_wins": ["X", "Y"],
  "long_bets": ["Z"]
}""",
            },
            {
                "role": "user",
                "content": f"STARTUPS (ordenadas por score):\n{scores_text}",
            },
        ],
        model=model,
        max_tokens=2048,
    )

    score_map = {s.startup_name: s for s in scores}
    ranked = []
    for i, r in enumerate(data.get("rankings", [])):
        name = r.get("startup_name", "")
        if name not in score_map:
            # fallback: usa posição da sorted list
            name = sorted_scores[i].startup_name if i < len(sorted_scores) else name
        ranked.append(RankedStartup(
            position=i + 1,
            startup_name=name,
            score=score_map.get(name, sorted_scores[i] if i < len(sorted_scores) else sorted_scores[0]),
            highlight=r.get("highlight", ""),
            action=r.get("action", ""),
        ))

    return RankingReport(
        ranked=ranked,
        strategic_summary=data.get("strategic_summary", ""),
        top_pick=data.get("top_pick", sorted_scores[0].startup_name if sorted_scores else ""),
        quick_wins=data.get("quick_wins", []),
        long_bets=data.get("long_bets", []),
    )
