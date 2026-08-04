import json
import os
import time
import cohere
from dotenv import load_dotenv
from pipeline.config.settings import (
    COHERE_CHAT_MODEL, PESO_AI_CLASS, PESO_SETOR,
    PESO_EVIDENCIA, PESO_MOMENTUM
)
from pipeline.db.connection import execute_query, fetch_one
from pipeline.utils.rate_limiter import cohere_wait

load_dotenv()

co_chat = cohere.ClientV2(os.environ["COHERE_API_KEY"])

PROMPT_CLASSIFICACAO = """Você é um analista de startups classificado. Dados os dados de uma startup e suas evidências, classifique em:

1. AI-native / AI-enabled / non-AI:
   - ai-native: IA é o produto central da empresa. Combina software, agentes de IA, dados proprietários e automação para entregar valor.
   - ai-enabled: usa IA como ferramenta interna, mas o produto principal é outro. Pode ser wrapper de LLM sem diferenciação.
   - non-ai: não usa IA de forma relevante.

2. Ramo principal: escolha UM entre healthtech, fintech, agritech, edtech, legaltech, retailtech, industria4, logistica, cybersecurity, energia, midia, proptech

3. Gaps identificados: liste os gaps técnicos que a startup tem com base nas evidências (máximo 3)

4. score_ai: 0.0 a 1.0 (o quão claramente é AI-native)

Responda APENAS com JSON:
{{
  "ai_classification": "ai-native|ai-enabled|non-ai",
  "ramo_principal": "healthtech|fintech|...",
  "score_ai": 0.0-1.0,
  "gaps_identificados": ["gap1", "gap2"],
  "justificativa": "breve justificativa"
}}

Startup: {nome}
Descrição: {descricao}
Produto: {produto}
Tecnologias detectadas: {tecnologias}
Evidências disponíveis: {evidencias}
"""


def _classificar_com_llm(startup: dict) -> dict | None:
    prompt = PROMPT_CLASSIFICACAO.format(
        nome=startup.get("nome", "desconhecida"),
        descricao=startup.get("descricao", "") or "",
        produto=startup.get("produto_principal", "") or "",
        tecnologias=", ".join(startup.get("tecnologias_detectadas", [])),
        evidencias=", ".join(startup.get("fontes_url", []))
    )

    for tentativa in range(1, 4):
        try:
            cohere_wait()
            resposta = co_chat.chat(
                model=COHERE_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )
            texto = resposta.message.content[0].text.strip()
            if texto.startswith("```"):
                texto = texto.split("\n", 1)[1]
            if texto.endswith("```"):
                texto = texto.rsplit("\n", 1)[0]
            return json.loads(texto.strip())
        except Exception as e:
            if tentativa == 3:
                return None
            time.sleep(5 * (2 ** (tentativa - 1)))


def _calcular_score_fit(resultado_llm: dict, startup: dict, setor_relevance: float) -> float:
    score_ai_map = {"ai-native": 1.0, "ai-enabled": 0.6, "non-ai": 0.1}
    score_ai = score_ai_map.get(resultado_llm.get("ai_classification", "non-ai"), 0.1)

    return (
        PESO_AI_CLASS * score_ai +
        PESO_SETOR * setor_relevance +
        PESO_EVIDENCIA * 0.5 +
        PESO_MOMENTUM * 0.3
    ) * 100


def _detectar_tecnologias_nvidia(texto: str | None) -> tuple[bool, list[str]]:
    if not texto:
        return False, []
    nvidia_techs = [
        "cuda", "nim", "triton", "tensorrt", "nemo", "rapids",
        "cudf", "cuml", "riva", "omniverse", "isaac", "clara",
        "morpheus", "ai enterprise", "inception"
    ]
    texto_lower = texto.lower()
    encontradas = [t for t in nvidia_techs if t in texto_lower]
    return len(encontradas) > 0, encontradas


def run_classifier(startups: list[dict], setor_relevance: float = 0.5) -> list[dict]:
    classificadas = []

    for startup in startups:
        if not startup.get("nome"):
            continue

        print(f"[Classifier] Classificando: {startup.get('nome')}")
        resultado = _classificar_com_llm(startup)
        if not resultado:
            continue

        usa_nvidia, techs_detectadas = _detectar_tecnologias_nvidia(
            f"{startup.get('descricao', '')} {' '.join(startup.get('tecnologias_detectadas', []))}"
        )

        score_fit = _calcular_score_fit(resultado, startup, setor_relevance)

        startup_entry = {
            "startup_id": startup.get("id"),
            "nome": startup.get("nome"),
            "website": startup.get("website"),
            "ai_classification": resultado.get("ai_classification", "non-ai"),
            "ramo_principal": resultado.get("ramo_principal"),
            "usa_nvidia": usa_nvidia,
            "nvidia_confidence": 0.8 if usa_nvidia else 0.0,
            "nvidia_techs_detectadas": techs_detectadas,
            "gaps_identificados": resultado.get("gaps_identificados", []),
            "score_fit_nvidia": round(score_fit, 1),
            "justificativa": resultado.get("justificativa", "")
        }

        if startup.get("id"):
            execute_query(
                """INSERT OR IGNORE INTO classificacoes
                (startup_id, ai_classification, ramo_principal, usa_nvidia, nvidia_confidence,
                 nvidia_techs_detectadas, gaps_identificados, score_fit_nvidia, justificativa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    startup["id"], startup_entry["ai_classification"],
                    startup_entry["ramo_principal"], 1 if startup_entry["usa_nvidia"] else 0,
                    startup_entry["nvidia_confidence"],
                    json.dumps(startup_entry["nvidia_techs_detectadas"]),
                    json.dumps(startup_entry["gaps_identificados"]),
                    startup_entry["score_fit_nvidia"],
                    startup_entry["justificativa"]
                )
            )

        classificadas.append(startup_entry)
        time.sleep(1)

    print(f"[Classifier] Classificadas: {len(classificadas)} startups")
    return classificadas
