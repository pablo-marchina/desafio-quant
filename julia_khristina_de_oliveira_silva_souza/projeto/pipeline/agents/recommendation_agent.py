import json
import os
import time
import cohere
from dotenv import load_dotenv
from pipeline.config.settings import COHERE_CHAT_MODEL, MAX_RECOMENDACOES_POR_STARTUP
from pipeline.db.connection import execute_query
from pipeline.utils.rate_limiter import cohere_wait

load_dotenv()

co_chat = cohere.ClientV2(os.environ["COHERE_API_KEY"])

PROMPT_RECOMENDACAO = """Você é um especialista em recomendar tecnologias NVIDIA para startups brasileiras.

Com base nos chunks de conhecimento recuperados e no perfil da startup, gere recomendações priorizadas.

Perfil da startup:
- Nome: {nome}
- Ramo: {ramo}
- Gaps identificados: {gaps}
- Classificação IA: {classificacao}
- Score Fit NVIDIA: {score_fit}

Chunks de conhecimento recuperados:
{chunks}

Exemplos de recomendação:
1. Startup usa LLMs em atendimento ao cliente via API externa → NIM, NeMo Guardrails, Triton
2. Startup processa dados tabulares → RAPIDS, cuDF, cuML
3. Startup de voz/call center → NVIDIA Riva, NIM
4. Startup de saúde → Clara, NIM, NeMo Guardrails, AI Enterprise
5. Startup de robótica/simulação → Isaac, Omniverse
6. Startup com latência de inferência → Triton, TensorRT-LLM
7. Startup precisa de governança em agentes → NeMo Guardrails

Responda APENAS com JSON array, sem preamble:
[
  {{
    "rank": 1,
    "tecnologia": "NVIDIA NIM",
    "categoria": "inferencia_deploy",
    "justificativa_tecnica": "...",
    "justificativa_negocio": "...",
    "nivel_prioridade": "alta|media|baixa",
    "complexidade_implementacao": "baixa|media|alta",
    "melhor_encaixe": "Explicação curta (1-2 frases) de por que esta tecnologia NVIDIA é a melhor opção para esta startup, considerando seus gaps, setor e maturidade.",
    "proxima_acao_sugerida": "...",
    "evidencias_usadas": ["url1", "url2"],
    "url_referencia": "https://..."
  }}
]

Máximo de {max_recomendacoes} recomendações. Cada campo é obrigatório.
"""


def _chat_com_retry(prompt: str, tentativas: int = 3, espera_base: int = 5) -> str:
    for tentativa in range(1, tentativas + 1):
        try:
            cohere_wait()
            resposta = co_chat.chat(
                model=COHERE_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000
            )
            return resposta.message.content[0].text
        except Exception as e:
            if tentativa == tentativas:
                raise
            espera = espera_base * (2 ** (tentativa - 1))
            print(f"[Recommendation] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando novamente em {espera}s...")
            time.sleep(espera)


def _formatar_chunks(chunks: list[dict]) -> str:
    linhas = []
    for c in chunks[:5]:
        linhas.append(f"- {c.get('tech', '')} (score: {c.get('relevance_score', 0):.2f}): {c.get('texto_resumido', '')}")
    return "\n".join(linhas)


def _gerar_recomendacoes(startup: dict) -> list[dict] | None:
    chunks = startup.get("chunks_aprovados", [])
    if not chunks:
        return None

    prompt = PROMPT_RECOMENDACAO.format(
        nome=startup.get("startup_nome", ""),
        ramo=startup.get("ramo", ""),
        gaps=", ".join(startup.get("gaps", [])),
        classificacao="ai-native",
        score_fit="85",
        chunks=_formatar_chunks(chunks),
        max_recomendacoes=MAX_RECOMENDACOES_POR_STARTUP
    )

    for _ in range(2):
        try:
            texto = _chat_com_retry(prompt)
            texto_limpo = texto.strip()
            if texto_limpo.startswith("```"):
                texto_limpo = texto_limpo.split("\n", 1)[1]
            if texto_limpo.endswith("```"):
                texto_limpo = texto_limpo.rsplit("\n", 1)[0]
            return json.loads(texto_limpo.strip())
        except (json.JSONDecodeError, Exception):
            continue
    return None


def _salvar_recomendacoes(startup_id: str | None, recomendacoes: list[dict]):
    if not startup_id:
        return
    for rec in recomendacoes:
        from pipeline.db.connection import fetch_one
        existente = fetch_one(
            "SELECT id FROM recomendacoes WHERE startup_id = ? AND tecnologia = ?",
            (startup_id, rec.get("tecnologia"))
        )
        if existente:
            print(f"  [Recommendation] Duplicata ignorada: {rec.get('tecnologia')} já existe para esta startup")
            continue
        execute_query(
            """INSERT INTO recomendacoes
            (startup_id, rank, tecnologia, categoria, justificativa_tecnica, justificativa_negocio,
             nivel_prioridade, complexidade_implementacao, melhor_encaixe, proxima_acao_sugerida, evidencias_usadas, url_referencia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                startup_id, rec.get("rank"), rec.get("tecnologia"), rec.get("categoria"),
                rec.get("justificativa_tecnica"), rec.get("justificativa_negocio"),
                rec.get("nivel_prioridade"), rec.get("complexidade_implementacao"),
                rec.get("melhor_encaixe"),
                rec.get("proxima_acao_sugerida"),
                json.dumps(rec.get("evidencias_usadas", [])),
                rec.get("url_referencia")
            )
        )


def run_recommendation_agent(recomendacoes_rag: list[dict]) -> list[dict]:
    recomendacoes_finais = []

    for item in recomendacoes_rag:
        nome = item.get("startup_nome", "desconhecida")
        print(f"[Recommendation] Gerando recomendações para: {nome}")

        recs = _gerar_recomendacoes(item)
        if not recs:
            continue

        startup_id = item.get("startup_id")
        _salvar_recomendacoes(startup_id, recs)

        recomendacoes_finais.append({
            "startup_id": startup_id,
            "startup_nome": nome,
            "recomendacoes": recs[:MAX_RECOMENDACOES_POR_STARTUP]
        })

        time.sleep(1)

    print(f"[Recommendation] {len(recomendacoes_finais)} startups com recomendações finais")
    return recomendacoes_finais
