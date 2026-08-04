from models.briefing import BriefingReport
from config.llm import chat_json, DEFAULT_MODEL
from pydantic import BaseModel


class SynergyPoint(BaseModel):
    title: str
    detail: str


class SynergyResult(BaseModel):
    has_synergy: bool
    synergy_points: list[SynergyPoint]
    integration_opportunity: str
    no_synergy_reason: str = ""


async def analyze_synergy(
    target: BriefingReport,
    peer: BriefingReport,
    model: str = DEFAULT_MODEL,
) -> SynergyResult:
    t = target.startup
    p = peer.startup

    target_ctx = f"""
Nome: {t.name}
Setor: {t.sector or 'N/A'}
Descrição: {t.description or 'N/A'}
Produtos: {', '.join(t.products) if t.products else 'N/A'}
Casos de uso: {', '.join(t.use_cases) if t.use_cases else 'N/A'}
Stack: {', '.join(t.tech_stack) if t.tech_stack else 'N/A'}
Modelo de negócio: {t.business_model or 'N/A'}
Mercado-alvo: {t.target_market or 'N/A'}
"""

    peer_ctx = f"""
Nome: {p.name}
Setor: {p.sector or 'N/A'}
Descrição: {p.description or 'N/A'}
Produtos: {', '.join(p.products) if p.products else 'N/A'}
Casos de uso: {', '.join(p.use_cases) if p.use_cases else 'N/A'}
Stack: {', '.join(p.tech_stack) if p.tech_stack else 'N/A'}
Modelo de negócio: {p.business_model or 'N/A'}
Mercado-alvo: {p.target_market or 'N/A'}
"""

    shared_nvidia = list(
        set(r.nvidia_tech for r in (target.recommendations or []))
        & set(r.nvidia_tech for r in (peer.recommendations or []))
    )

    data = await chat_json(
        messages=[
            {
                "role": "system",
                "content": """Você é um analista de ecossistema de startups de IA brasileiras.
Sua tarefa: dado um startup ALVO e um startup PAR, analisar se e como o PAR pode ajudar o ALVO.

Foque em:
- Produtos/capacidades do PAR que resolvem problemas concretos do ALVO
- Dados, APIs ou infraestrutura do PAR que o ALVO pode usar
- Casos de uso específicos onde a colaboração faz sentido
- Oportunidade de integração via tecnologias NVIDIA compartilhadas

Seja específico — cite produtos reais, não generalidades.
Se não houver sinergia real, retorne has_synergy: false.

Retorne JSON:
{
  "has_synergy": true,
  "synergy_points": [
    {"title": "título curto", "detail": "detalhe específico de como o PAR ajuda o ALVO"}
  ],
  "integration_opportunity": "como integrar via NVIDIA ou tech compartilhada",
  "no_synergy_reason": "motivo se has_synergy=false, senão string vazia"
}

Gere 2-4 synergy_points se has_synergy=true. Seja direto e técnico.""",
            },
            {
                "role": "user",
                "content": f"""STARTUP ALVO:
{target_ctx}

STARTUP PAR (que pode ajudar o alvo):
{peer_ctx}

Tecnologias NVIDIA em comum: {', '.join(shared_nvidia) if shared_nvidia else 'nenhuma identificada'}

Analise: como {p.name} pode ajudar {t.name}?""",
            },
        ],
        model=model,
        max_tokens=1024,
    )

    points = [
        SynergyPoint(title=sp["title"], detail=sp["detail"])
        for sp in data.get("synergy_points", [])
        if isinstance(sp, dict) and "title" in sp and "detail" in sp
    ]

    return SynergyResult(
        has_synergy=bool(data.get("has_synergy", False)),
        synergy_points=points,
        integration_opportunity=data.get("integration_opportunity", ""),
        no_synergy_reason=data.get("no_synergy_reason", ""),
    )
