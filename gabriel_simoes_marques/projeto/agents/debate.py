"""
Adversarial debate between two BDI agents defending competing startups
for NVIDIA Inception recommendation.

BDI model:
  Beliefs  → facts about both startups (from graph + briefing reports)
  Desires  → win the debate to secure NVIDIA partnership for their startup
  Intentions → planned arguments derived from beliefs before debate starts
"""

from models.debate import BDIState, DebateMove, DebateRoundType, DebateVerdict, DebateResult
from models.briefing import BriefingReport
from config.llm import chat_json, DEFAULT_MODEL


def _build_context(report: BriefingReport) -> str:
    s = report.startup
    recs = "\n".join(f"  - {r.nvidia_tech} ({r.priority.value}): {r.technical_justification}" for r in report.recommendations)
    return f"""
Startup: {s.name}
Setor: {s.sector}
Classificação: {s.classification}
Descrição: {s.description}
Stack: {', '.join(s.tech_stack)}
Funding: {f"USD {s.funding_usd:,.0f}" if s.funding_usd else "não informado"}
Fundadores: {', '.join(s.founders)}
Recomendações NVIDIA:
{recs}
Briefing: {report.summary}
""".strip()


async def _form_intentions(
    defender: str,
    context_a: str,
    context_b: str,
    model: str,
) -> BDIState:
    """Fase BDI: agente forma intenções antes de debater."""
    data = await chat_json(
        messages=[
            {
                "role": "system",
                "content": f"""Você é um agente de IA com a seguinte estrutura BDI:

DESIRES: Provar que {defender} é a melhor escolha para o programa NVIDIA Inception, resultando em partnership, acesso a GPUs e suporte técnico NVIDIA.

Você tem acesso a informações de duas startups. Forme suas INTENTIONS: liste 4 argumentos técnicos e de negócio que vai usar no debate para defender {defender} e atacar o concorrente.

Retorne JSON:
{{
  "beliefs_summary": "resumo do que sei sobre ambas as startups",
  "intentions": ["argumento1", "argumento2", "argumento3", "argumento4"]
}}""",
            },
            {
                "role": "user",
                "content": f"STARTUP QUE DEFENDO ({defender}):\n{context_a}\n\nCONCORRENTE:\n{context_b}",
            },
        ],
        model=model,
        max_tokens=1024,
    )

    return BDIState(
        startup_name=defender,
        beliefs={"summary": data.get("beliefs_summary", ""), "context_a": context_a, "context_b": context_b},
        desires=f"Provar que {defender} é a melhor escolha para NVIDIA Inception",
        intentions=data.get("intentions", []),
    )


async def _debate_move(
    bdi: BDIState,
    round_type: DebateRoundType,
    history: list[DebateMove],
    model: str,
) -> str:
    history_text = "\n".join([
        f"[{m.agent} - {m.round_type.value}]: {m.argument}"
        for m in history
    ]) or "Nenhuma rodada anterior."

    intentions_text = "\n".join(f"- {i}" for i in bdi.intentions)

    round_instructions = {
        DebateRoundType.opening: f"Apresente {bdi.startup_name} como a melhor escolha para NVIDIA Inception. Use 2-3 dos seus argumentos planejados. Seja direto e técnico.",
        DebateRoundType.attack: f"Ataque os pontos fracos do concorrente usando fatos. Questione a sustentabilidade, diferenciação técnica e fit com o ecossistema NVIDIA. Seja agressivo mas baseado em evidências.",
        DebateRoundType.rebuttal: f"Rebata os ataques do concorrente contra {bdi.startup_name}. Fortaleça seus argumentos mais fracos. Conclua com por que {bdi.startup_name} vence.",
    }

    data = await chat_json(
        messages=[
            {
                "role": "system",
                "content": f"""Você é um agente adversarial debatendo em nome de {bdi.startup_name}.

DESIRES: {bdi.desires}
INTENTIONS planejadas:
{intentions_text}

Instrução desta rodada: {round_instructions[round_type]}

Responda em português, máximo 150 palavras. Seja específico, técnico e persuasivo.
Retorne JSON: {{"argument": "seu argumento"}}""",
            },
            {
                "role": "user",
                "content": f"CONTEXTO DA SUA STARTUP:\n{bdi.beliefs['context_a']}\n\nCONCORRENTE:\n{bdi.beliefs['context_b']}\n\nHISTÓRICO DO DEBATE:\n{history_text}",
            },
        ],
        model=model,
        max_tokens=512,
    )

    return data.get("argument", "")


async def _judge(
    startup_a: str,
    startup_b: str,
    rounds: list[DebateMove],
    context_a: str,
    context_b: str,
    model: str,
) -> DebateVerdict:
    transcript = "\n\n".join([
        f"[{m.agent.upper()} — {m.round_type.value.upper()}]\n{m.argument}"
        for m in rounds
    ])

    data = await chat_json(
        messages=[
            {
                "role": "system",
                "content": """Você é um juiz neutro do programa NVIDIA Inception Brasil avaliando qual startup merece mais o partnership.

Critérios de avaliação (peso em %):
- Fit técnico com ecossistema NVIDIA (30%)
- Potencial de crescimento no mercado (25%)
- Diferenciação vs concorrentes (20%)
- Qualidade dos argumentos no debate (15%)
- Timing e urgência da parceria (10%)

Analise o debate com imparcialidade. Dê notas de 0-10.

Retorne JSON:
{
  "winner": "nome da startup vencedora",
  "score_a": 7,
  "score_b": 8,
  "reasoning": "análise detalhada de 3-5 frases",
  "nvidia_recommendation": "ação concreta recomendada para o time NVIDIA"
}""",
            },
            {
                "role": "user",
                "content": f"STARTUP A — {startup_a}:\n{context_a}\n\nSTARTUP B — {startup_b}:\n{context_b}\n\nTRANSCRITO DO DEBATE:\n{transcript}",
            },
        ],
        model=model,
        max_tokens=1024,
    )

    return DebateVerdict(
        winner=data.get("winner", startup_a),
        score_a=int(data.get("score_a", 5)),
        score_b=int(data.get("score_b", 5)),
        reasoning=data.get("reasoning", ""),
        nvidia_recommendation=data.get("nvidia_recommendation", ""),
    )


async def run_debate(
    report_a: BriefingReport,
    report_b: BriefingReport,
    model_a: str = DEFAULT_MODEL,
    model_b: str = DEFAULT_MODEL,
    judge_model: str = DEFAULT_MODEL,
) -> DebateResult:
    context_a = _build_context(report_a)
    context_b = _build_context(report_b)

    bdi_a, bdi_b = await asyncio.gather(
        _form_intentions(report_a.startup.name, context_a, context_b, model_a),
        _form_intentions(report_b.startup.name, context_b, context_a, model_b),
    )

    rounds: list[DebateMove] = []

    for round_type in [DebateRoundType.opening, DebateRoundType.attack, DebateRoundType.rebuttal]:
        arg_a, arg_b = await asyncio.gather(
            _debate_move(bdi_a, round_type, rounds, model_a),
            _debate_move(bdi_b, round_type, rounds, model_b),
        )
        rounds.append(DebateMove(agent=report_a.startup.name, round_type=round_type, argument=arg_a))
        rounds.append(DebateMove(agent=report_b.startup.name, round_type=round_type, argument=arg_b))

    verdict = await _judge(
        report_a.startup.name, report_b.startup.name,
        rounds, context_a, context_b, judge_model,
    )

    return DebateResult(
        startup_a=report_a.startup.name,
        startup_b=report_b.startup.name,
        model=f"{model_a} vs {model_b}",
        rounds=rounds,
        verdict=verdict,
    )


import asyncio
