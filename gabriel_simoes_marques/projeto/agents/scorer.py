"""
Scorer agent: avalia fit de uma startup com a NVIDIA em 5 dimensões.

Dimensões e pesos:
  technical_fit    30%  — stack GPU-compatível, workloads aceleráveis
  ai_maturity      25%  — AI-native, modelos próprios, dados proprietários
  market_potential 20%  — TAM, B2B, setor estratégico NVIDIA
  strategic_value  15%  — showcase, efeito multiplicador no ecossistema
  urgency          10%  — funding disponível, gargalo solucionável agora

Score total = weighted avg × 10 → 0-100
Tier: S=80+, A=65+, B=50+, C=<50
"""

from models.briefing import BriefingReport
from models.score import StartupScore, DimensionScore
from config.llm import chat_json, DEFAULT_MODEL

WEIGHTS = {
    "technical_fit": 0.30,
    "ai_maturity": 0.25,
    "market_potential": 0.20,
    "strategic_value": 0.15,
    "urgency": 0.10,
}

SYSTEM_PROMPT = """Você é um analista do programa NVIDIA Inception avaliando startups brasileiras de IA para fit de parceria.

Responda sempre em português do Brasil.

Pontue cada dimensão de 0 a 10:

FIT TÉCNICO (30%)
10 = workloads core GPU (inferência LLM, CV, IA generativa), stack nativa CUDA
7  = ML em produção, Python/PyTorch/TF, caminho claro para aceleração GPU
4  = algum uso de ML, necessidade de GPU não clara
1  = sem potencial significativo de workload GPU

MATURIDADE DE IA (25%)
10 = AI-native, modelos proprietários + dados, ML em produção em escala
7  = pipeline de ML robusto, alguma IP proprietária
4  = AI-enabled, usa APIs/modelos de terceiros
1  = não-IA, uso superficial de IA

POTENCIAL DE MERCADO (20%)
10 = grande TAM B2B, alto crescimento, setor onde NVIDIA domina (saúde IA, fintech ML, visão industrial)
7  = B2B sólido, mercado em crescimento
4  = B2B/B2C misto ou mercado de nicho
1  = mercado pequeno, sem caminho claro de monetização GPU

VALOR ESTRATÉGICO (15%)
10 = pronto para showcase, efeito multiplicador (cada cliente usa tech NVIDIA)
7  = caso de referência forte, visível no mercado
4  = contribuição moderada ao ecossistema
1  = impacto mínimo no ecossistema NVIDIA

URGÊNCIA (10%)
10 = bem financiado, escalando ativamente, gargalo GPU é bloqueador atual
7  = financiado, fase de crescimento, parceria NVIDIA oportuna
4  = early stage, parceria orientada ao futuro
1  = sem urgência clara ou orçamento para agir

Retorne JSON:
{
  "technical_fit": {"score": 8, "rationale": "..."},
  "ai_maturity": {"score": 7, "rationale": "..."},
  "market_potential": {"score": 6, "rationale": "..."},
  "strategic_value": {"score": 7, "rationale": "..."},
  "urgency": {"score": 8, "rationale": "..."},
  "recommendation": "ação concreta para o time NVIDIA em 1-2 frases"
}"""


def _calc_total(scores: dict) -> int:
    total = sum(scores[dim] * weight for dim, weight in WEIGHTS.items())
    return round(total * 10)


def _tier(total: int) -> str:
    if total >= 80: return "S"
    if total >= 65: return "A"
    if total >= 50: return "B"
    return "C"


async def score_startup(report: BriefingReport, model: str = DEFAULT_MODEL) -> StartupScore:
    s = report.startup
    recs = "\n".join(f"- {r.nvidia_tech} ({r.priority.value}): {r.technical_justification}" for r in report.recommendations)

    context = f"""
Startup: {s.name}
Setor: {s.sector}
Classificação: {s.classification}
Descrição: {s.description}
Stack: {', '.join(s.tech_stack)}
Funding: USD {f"{s.funding_usd:,.0f}" if s.funding_usd else "N/A"}
Fundadores: {', '.join(s.founders)}
Recomendações NVIDIA já identificadas:
{recs}
Briefing: {report.summary}
""".strip()

    data = await chat_json(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        model=model,
        max_tokens=1024,
        temperature=0,
    )

    raw_scores = {dim: data[dim]["score"] for dim in WEIGHTS}
    total = _calc_total(raw_scores)

    return StartupScore(
        startup_name=s.name,
        technical_fit=DimensionScore(**data["technical_fit"]),
        ai_maturity=DimensionScore(**data["ai_maturity"]),
        market_potential=DimensionScore(**data["market_potential"]),
        strategic_value=DimensionScore(**data["strategic_value"]),
        urgency=DimensionScore(**data["urgency"]),
        total=total,
        tier=_tier(total),
        recommendation=data.get("recommendation", ""),
    )
