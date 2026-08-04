import json
import os
import time
import cohere
from dotenv import load_dotenv
from pipeline.config.settings import COHERE_CHAT_MODEL
from pipeline.utils.rate_limiter import cohere_wait

load_dotenv()

co_chat = cohere.ClientV2(os.environ["COHERE_API_KEY"])


def _carregar_setores() -> list[dict]:
    with open("pipeline/config/setores.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _carregar_fontes() -> dict:
    with open("pipeline/config/fontes_scraping.json", "r", encoding="utf-8") as f:
        return json.load(f)


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
            print(f"[SearchPlanner] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando de novo em {espera}s...")
            time.sleep(espera)


def gerar_queries(setor: dict, fontes: dict) -> list[dict]:

    prompt = (
        f"Você é um analista de startups brasileiras. Dado o setor abaixo, gere 6 queries de busca "
        f"para encontrar startups brasileiras ativas neste setor usando busca na web.\n\n"
        f"Setor: {setor['nome']}\n"
        f"Descrição: {setor['descricao']}\n"
        f"Keywords: {', '.join(setor['keywords'])}\n\n"
        f"Gere queries variadas:\n"
        f"- Umas focadas em listar startups do setor (ex: 'startups brasileiras de {setor['id']}')\n"
        f"- Umas focadas em notícias recentes de investimento (ex: '{setor['nome']} startup funding rodada investimento Brasil 2025')\n"
        f"- Umas focadas em premiações/lançamentos (ex: '{setor['nome']} startup prêmio lançamento 2025')\n\n"
        f"Responda APENAS com um JSON array, sem preamble, sem markdown:\n"
        f'[{{\"query\": \"...\", \"tipo_fonte\": \"web\", '
        f'\"setor\": \"{setor['id']}\", \"momentum_signals\": [\"...\"], \"prioridade\": 1}}]'
    )

    texto = _chat_com_retry(prompt)

    texto_limpo = texto.strip()
    if texto_limpo.startswith("```"):
        texto_limpo = texto_limpo.split("\n", 1)[1]
    if texto_limpo.endswith("```"):
        texto_limpo = texto_limpo.rsplit("\n", 1)[0]
    texto_limpo = texto_limpo.strip()

    return json.loads(texto_limpo)


def run_search_planner(setor_alvo: str) -> list[dict]:
    setores = _carregar_setores()
    setor = next((s for s in setores if s["id"] == setor_alvo), None)
    if not setor:
        raise ValueError(f"Setor '{setor_alvo}' não encontrado em setores.json")

    fontes = _carregar_fontes()
    return gerar_queries(setor, fontes)
