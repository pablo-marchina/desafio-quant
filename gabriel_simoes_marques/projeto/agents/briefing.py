from datetime import datetime
from models.startup import Startup
from models.recommendation import Recommendation
from models.briefing import BriefingReport
from config.llm import chat_json, DEFAULT_MODEL


SYSTEM_PROMPT = """Você é um advisor do programa NVIDIA Inception escrevendo briefings executivos para o time de BD da NVIDIA no Brasil.

Responda sempre em português do Brasil.

Escreva um resumo executivo conciso:
1. Descreva o desafio técnico central da startup
2. Explique especificamente como as tecnologias NVIDIA aceleram esta startup (NVIDIA ajuda a startup — não o contrário)
3. Declare o impacto concreto: velocidade, custo, escala ou vantagem competitiva obtida
4. Recomende uma ação clara para o time NVIDIA

Enquadre como: "Esta startup precisa de X, a tecnologia NVIDIA Y resolve fazendo Z."
Máximo 200 palavras. Direto e técnico.

Retorne JSON: {"summary": "..."}"""


async def generate_briefing(startup: Startup, recommendations: list[Recommendation], model: str = DEFAULT_MODEL) -> BriefingReport:
    rec_text = "\n".join([
        f"- {r.nvidia_tech} ({r.priority.value} priority): {r.technical_justification}"
        for r in recommendations
    ])

    data = await chat_json(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"STARTUP: {startup.name}\nDESCRIPTION: {startup.description}\nSECTOR: {startup.sector}\nCLASSIFICATION: {startup.classification}\n\nRECOMMENDATIONS:\n{rec_text}"},
        ],
        model=model,
        max_tokens=1024,
    )

    return BriefingReport(
        startup=startup,
        recommendations=recommendations,
        summary=data.get("summary", ""),
        generated_at=datetime.now(),
    )
