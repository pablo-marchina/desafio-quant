"""Classifier Agent: classifica a maturidade AI-native da startup (via LLM)."""

from __future__ import annotations

import json

from agents.llm import ask_llm, parse_json
from graph.state import StartupState

# Linguagens que sinalizam produção de ML/IA no GitHub (evidência positiva).
_ML_LANGUAGES = {"Python", "Jupyter Notebook"}

SYSTEM_PROMPT = """Você é um analista que classifica a maturidade em IA de startups.

NÍVEIS (escolha exatamente um):
3 = AI-native — produz: modelo próprio, fine-tuning, pipeline de treino, dados proprietários. IA é o núcleo.
2 = AI-enabled — consome com profundidade: integra APIs de IA com workflow próprio e diferenciação real.
1 = AI-wrapper — consome superficialmente: interface sobre uma API de terceiro, sem dados ou diferenciação.
0 = Non-AI — IA ausente ou apenas cosmética.

CHECKLIST (responda as 6, cada uma com "resposta" = sim/não/inconclusivo e "evidencia"):
1. Tem evidência de modelo próprio ou fine-tuning?
2. Há perfis técnicos de IA no time (ML Engineer, MLOps, AI Researcher)?
3. A stack técnica é identificável além de "usamos IA"?
4. Há menção a dados proprietários ou datasets exclusivos?
5. O produto seria substituível por um GPT wrapper genérico?
6. Há presença de VC ou funding relevante?

Quando houver um sinal do GitHub, ele é evidência POSITIVA para as perguntas 1 e 3:
repositórios públicos com linguagens de ML (Python/Jupyter) reforçam que a empresa
PRODUZ IA. Ele só é mostrado quando é positivo — a falta de menção ao GitHub não é
evidência de nada (muitas empresas mantêm o código de IA privado).

Use "inconclusivo" quando o dado não estiver disponível. Classifique com o que tem.

Responda APENAS com um objeto JSON válido neste formato:
{
  "checklist": [
    {"pergunta": 1, "resposta": "sim/não/inconclusivo", "evidencia": "..."}
  ],
  "level": 0,
  "level_name": "Non-AI/AI-wrapper/AI-enabled/AI-native",
  "rationale": "justificativa curta do nível escolhido"
}"""


def classifier_node(state: StartupState) -> dict:
    """Lê os dados da startup, responde o checklist e atribui o nível."""
    structured = state.get("structured", {})
    raw_text = state.get("raw_text", "")

    # GitHub entra APENAS como evidência positiva: só quando há linguagens de ML
    # públicas. Ausência de ML público não é sinal negativo (código de IA costuma
    # ser privado), então nesse caso nem mencionamos o GitHub.
    github = state.get("github", {})
    langs = github.get("languages") or []
    gh_block = ""
    if github.get("found") and any(lang in _ML_LANGUAGES for lang in langs):
        gh_block = (
            f"Sinal do GitHub (evidência de que PRODUZ IA): a org '{github.get('org')}' tem "
            f"{github.get('repos_count')} repos públicos com linguagens de ML {langs} "
            f"(ex.: {github.get('top_repos')}).\n\n"
        )

    user_prompt = (
        f"Dados estruturados da startup:\n"
        f"{json.dumps(structured, ensure_ascii=False, indent=2)}\n\n"
        f"{gh_block}"
        f"Trecho do site (apoio):\n{raw_text[:2000]}"
    )
    answer = ask_llm(SYSTEM_PROMPT, user_prompt, max_tokens=1000)
    result = parse_json(answer)

    return {
        "checklist": result.get("checklist", []),
        "level": result.get("level"),
        "level_name": result.get("level_name"),
        "rationale": result.get("rationale"),
    }
