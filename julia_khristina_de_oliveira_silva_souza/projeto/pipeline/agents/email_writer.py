import json
import os
import time
import cohere
from dotenv import load_dotenv
from pipeline.db.connection import fetch_one, fetch_all
from pipeline.config.settings import COHERE_CHAT_MODEL

load_dotenv()
_co = None

_PROMPT_EMAIL = """Você é um executivo de parcerias da NVIDIA escrevendo um email personalizado e persuasivo para o CEO/CTO de uma startup brasileira.

## Dados da Startup
- Nome: {nome}
- Setor: {setor}
- Estágio: {estagio}
- Cidade: {cidade}
- Funcionários: {funcionarios}
- Rodada de investimento: {rodada}
- Clientes: {clientes}
- Produto principal: {produto}
- Descrição: {descricao}
- Score de fit NVIDIA: {score_fit}/100

## Recomendação Principal da NVIDIA
- Produto: {rec_tecnologia}
- Por que se encaixa: {rec_encaixe}
- Justificativa de negócio: {rec_negocio}

## Tom e Regras
- Tom profissional, direto e persuasivo, sem ser agressivo
- Use os dados reais da startup para mostrar que a mensagem foi personalizada
- Explique APENAS o produto NVIDIA recomendado (não liste outros)
- Mostre 2-3 benefícios concretos e mensuráveis que a startup teria
- Sugira uma Call to Action clara (ex: "agendar uma conversa de 20 minutos")
- Mínimo 15 linhas, máximo 25 linhas
- Escreva em português brasileiro
- NÃO use markdown, asteriscos, ou formatação — apenas texto puro
- NÃO invente dados ou métricas que não estão nos dados fornecidos
- NÃO use saudações genéricas como "Prezado" ou "Caro" — use "Olá, equipe {nome}" ou "Olá, time {nome}"

Responda APENAS com o texto do email, sem explicações adicionais nem preâmbulo.
"""


def _get_co():
    global _co
    if _co is None:
        _co = cohere.ClientV2(os.environ["COHERE_API_KEY"])
    return _co


def _chat_com_retry(prompt: str, tentativas: int = 3, espera_base: int = 5) -> str:
    co = _get_co()
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = co.chat(
                model=COHERE_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )
            return resposta.message.content[0].text.strip()
        except Exception as e:
            if tentativa == tentativas:
                raise
            espera = espera_base * (2 ** (tentativa - 1))
            print(f"[EmailWriter] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando em {espera}s...")
            time.sleep(espera)


def gerar_email(startup_id: str, startup_data: dict | None = None) -> dict:
    if not startup_data:
        startup_data = fetch_one("SELECT * FROM startups WHERE id = ?", (startup_id,))
    if not startup_data:
        return {"erro": "Startup não encontrada"}

    classificacao = fetch_one(
        "SELECT * FROM classificacoes WHERE startup_id = ? ORDER BY classificado_em DESC LIMIT 1",
        (startup_id,)
    )
    recomendacoes = fetch_all(
        "SELECT * FROM recomendacoes WHERE startup_id = ? ORDER BY rank ASC LIMIT 3",
        (startup_id,)
    )

    rec = recomendacoes[0] if recomendacoes else {}

    prompt = _PROMPT_EMAIL.format(
        nome=startup_data.get("nome", ""),
        setor=startup_data.get("setor", ""),
        estagio=startup_data.get("estagio", ""),
        cidade=startup_data.get("cidade", ""),
        funcionarios=startup_data.get("numero_funcionarios_faixa", ""),
        rodada=startup_data.get("ultima_rodada_data", "") or startup_data.get("ultima_rodada_valor", ""),
        clientes="",
        produto=startup_data.get("produto_principal", ""),
        descricao=startup_data.get("descricao", ""),
        score_fit=classificacao.get("score_fit_nvidia", 50) if classificacao else 50,
        rec_tecnologia=rec.get("tecnologia", "soluções NVIDIA de IA"),
        rec_encaixe=rec.get("melhor_encaixe", ""),
        rec_negocio=rec.get("justificativa_negocio", "")
    )

    try:
        texto = _chat_com_retry(prompt)
        return {"email": texto, "assunto": f"[NVIDIA] Oportunidade de parceria para {startup_data.get('nome', '')}"}
    except Exception as e:
        return {"erro": str(e)}
