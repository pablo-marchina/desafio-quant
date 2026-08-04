from models.startup import Startup
from models.recommendation import Recommendation, Priority, Complexity
from rag.query import query_nvidia_techs
from config.llm import chat_json, DEFAULT_MODEL


SYSTEM_PROMPT = """Você é um arquiteto sênior de soluções NVIDIA analisando startups de IA brasileiras para o programa NVIDIA Inception.

Responda sempre em português do Brasil.

Dado o perfil da startup e fatos relevantes do grafo de conhecimento NVIDIA:
1. Identifique quais tecnologias NVIDIA melhor atendem as necessidades técnicas desta startup
2. Enquadre como: "Esta startup precisa de X, e a tecnologia NVIDIA Y resolve isso fazendo Z"
3. Priorize com base no impacto imediato no negócio

Retorne JSON:
{
  "recommendations": [
    {
      "nvidia_tech": "NVIDIA NIM",
      "technical_justification": "...",
      "business_justification": "...",
      "priority": "high",
      "complexity": "medium",
      "next_action": "...",
      "evidence_used": ["fato1"]
    }
  ]
}

Priority: high=fit imediato, medium=potencial forte, low=futuro
Complexity: high=meses, medium=semanas, low=dias
Gere 2-5 recomendações. Seja específico e técnico."""


async def generate_recommendations(startup: Startup, graphiti, model: str = DEFAULT_MODEL) -> list[Recommendation]:
    startup_context = f"""
Startup: {startup.name}
Sector: {startup.sector or 'unknown'}
Description: {startup.description or 'no description'}
Tech Stack: {', '.join(startup.tech_stack) if startup.tech_stack else 'unknown'}
Classification: {startup.classification}
"""

    # gera queries de busca baseadas no perfil da startup
    queries_data = await chat_json(
        messages=[
            {"role": "system", "content": "Dado o perfil de uma startup, gere 3 queries de busca descrevendo os desafios técnicos centrais onde tecnologia NVIDIA pode ajudar. Retorne JSON: {\"queries\": [\"query1\", \"query2\", \"query3\"]}"},
            {"role": "user", "content": startup_context},
        ],
        model=model,
        max_tokens=512,
    )
    queries = queries_data.get("queries", [startup.description or startup.name])

    # busca no grafo NVIDIA
    edges = await query_nvidia_techs(queries, graphiti, num_results=5)
    graph_facts = "\n".join([f"- [{e.name}] {e.fact}" for e in edges[:20]])

    # gera recomendações com base nas evidências do grafo
    data = await chat_json(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"STARTUP:\n{startup_context}\n\nNVIDIA GRAPH FACTS:\n{graph_facts}\n\nGenerate recommendations:"},
        ],
        model=model,
        max_tokens=2048,
    )

    recommendations = []
    for r in data.get("recommendations", []):
        try:
            recommendations.append(Recommendation(
                nvidia_tech=r["nvidia_tech"],
                technical_justification=r["technical_justification"],
                business_justification=r["business_justification"],
                priority=Priority(r.get("priority", "medium")),
                complexity=Complexity(r.get("complexity", "medium")),
                next_action=r.get("next_action", ""),
                evidence_used=r.get("evidence_used", []),
            ))
        except Exception:
            continue

    return recommendations
