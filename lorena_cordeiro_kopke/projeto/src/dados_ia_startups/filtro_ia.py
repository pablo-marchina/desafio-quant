from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SAIDA = _RAIZ / "data" / "jsons" / "vereditos_ia"

THRESHOLD = 3

# Pontuação máxima aproveitada por camada (evita inflação por múltiplos sinais iguais)
_TETO_CAMADA: dict[str, int] = {
    "institucional": 3,
    "neofeed":       3,
    "gupy_vagas":    2,
    "imprensa":      2,
}

_PALAVRAS_IA = re.compile(
    r'\b('
    r'IA|AI|intelig[eê]ncia artificial|artificial intelligence'
    r'|machine learning|deep learning|LLM|GPT|chatbot'
    r'|modelo preditivo|MLOps|data science|algoritmo'
    r'|automa[çc][ãa]o inteligente|rede neural|neural'
    r'|generativ[ao]|gen.?ai|copilot'
    r'|processamento de linguagem|NLP|computer vision'
    r'|reconhecimento de imagem|aprendizado de m[áa]quina'
    r'|retrieval.augmented|embeddings?|fine.tuning|finetuning'
    r'|vector.database|banco.vetorial|feature.store|llmops'
    r'|foundation.model|large.language.model|multimodal'
    r'|hugging.face|langchain|openai|anthropic|claude|gemini|llama'
    r')\b',
    re.IGNORECASE,
)

# Vagas diretamente ligadas a IA/ML
_CARGOS_IA = re.compile(
    r'\b('
    r'cientista de dados|data scientist'
    r'|engenheiro.{0,15}(IA|intelig[eê]ncia|machine|ML)'
    r'|especialista.{0,15}(IA|intelig[eê]ncia|machine|ML)'
    r'|ML engineer|machine learning|deep learning'
    r'|intelig[eê]ncia artificial'
    r')\b',
    re.IGNORECASE,
)

# Vagas de dados sem menção explícita a IA
_CARGOS_DADOS = re.compile(
    r'\b(engenheiro de dados|data engineer|analytics|big data|analista de dados)\b',
    re.IGNORECASE,
)

# Títulos de artigos que indicam tendência de mercado, não uso pela empresa
_TENDENCIA = re.compile(
    r'(nova safra|bilion[áa]rios|corrida por'
    r'|onda de|mercado de IA|setor de IA|boom da IA)',
    re.IGNORECASE,
)

# Padrões que indicam a empresa é investidora, não a empresa de IA em si.
# Apenas verbos que são inequivocamente papel financeiro — nunca descrevem uso de IA.
# ex: "IA para dentistas atrai Triaxis" → Triaxis é investidora
# EVITADO: investe, aporta, entra, apoia, lidera — também descrevem empresas que USAM IA
_PAPEL_INVESTIDOR = re.compile(
    r'\b(atrai|atraem|ancora|ancoram|financia|financiam|co-lidera|co-investem)\b',
    re.IGNORECASE,
)


def _score_sinal(camada: str, encontrado: bool, evidencia: str, nome_empresa: str) -> tuple[int, str]:
    """Retorna (pontuação, razão) para um único sinal."""
    if not encontrado:
        return 0, ""

    ev = evidencia or ""
    tem_ia = bool(_PALAVRAS_IA.search(ev))

    if camada == "institucional":
        if tem_ia:
            return 3, "site menciona IA explicitamente"
        return 0, "encontrado sem menção a IA no site"

    if camada == "neofeed":
        if not tem_ia:
            return 0, "artigo sem menção a IA"
        if _TENDENCIA.search(ev):
            return 1, "artigo sobre tendência de mercado"
        # Empresa aparece como investidora/parceira, não como a empresa de IA
        if _PAPEL_INVESTIDOR.search(ev):
            return 1, "empresa mencionada como investidora/parceira, não como usuária de IA"
        return 3, "artigo sobre IA diretamente relacionado à empresa"

    if camada == "gupy_vagas":
        if _CARGOS_IA.search(ev):
            return 2, f"vaga de IA/ML: {ev[:60]}"
        if _CARGOS_DADOS.search(ev):
            return 1, f"vaga de dados: {ev[:60]}"
        if encontrado:
            return 1, f"vaga relevante: {ev[:60]}"
        return 0, ""

    if camada == "imprensa":
        if tem_ia:
            return 2, "imprensa menciona IA"
        return 0, "encontrado sem menção a IA na imprensa"

    return 0, ""


def _avaliar_empresa(empresa_id: int, nome: str, sinais: list[dict]) -> dict:
    """Agrega sinais da empresa e calcula pontuação final."""
    # Melhor score por camada (evita somar múltiplas vagas gupy, etc.)
    melhor_por_camada: dict[str, tuple[int, str, str]] = {}

    for sinal in sinais:
        camada = sinal["camada"]
        encontrado = sinal.get("encontrado") or False
        evidencia = sinal.get("evidencia") or ""

        score, razao = _score_sinal(camada, encontrado, evidencia, nome)
        if score <= 0:
            continue

        atual = melhor_por_camada.get(camada)
        if atual is None or score > atual[0]:
            melhor_por_camada[camada] = (score, razao, evidencia)

    pontuacao = sum(v[0] for v in melhor_por_camada.values())

    sinais_ativos = [
        {
            "camada": camada,
            "score": score,
            "razao": razao,
            "evidencia": ev[:120] if ev else None,
        }
        for camada, (score, razao, ev) in melhor_por_camada.items()
    ]

    return {
        "empresa_id": empresa_id,
        "nome": nome,
        "pontuacao": pontuacao,
        "veredito": pontuacao >= THRESHOLD,
        "sinais_ativos": sinais_ativos,
    }


def _carregar_dados() -> tuple[dict[int, str], list[dict]]:
    """Retorna mapa id→nome e todos os sinais do Supabase."""
    empresas = supabase.table("empresas").select("id, nome").execute().data
    mapa_nomes = {int(e["id"]): e["nome"] for e in empresas}

    sinais = supabase.table("sinais_ia").select(
        "empresa_id, camada, encontrado, evidencia"
    ).execute().data

    return mapa_nomes, sinais


def _agrupar_por_empresa(sinais: list[dict]) -> dict[int, list[dict]]:
    agrupado: dict[int, list[dict]] = {}
    for s in sinais:
        eid = int(s["empresa_id"])
        agrupado.setdefault(eid, []).append(s)
    return agrupado


def _gravar_supabase(avaliacoes: list[dict]) -> None:
    registros = [
        {
            "empresa_id": a["empresa_id"],
            "pontuacao": a["pontuacao"],
            "veredito": a["veredito"],
            "sinais_ativos": a["sinais_ativos"],
            "avaliado_em": datetime.now(timezone.utc).isoformat(),
        }
        for a in avaliacoes
    ]
    supabase.table("avaliacoes_ia").upsert(
        registros, on_conflict="empresa_id"
    ).execute()
    print(f"[banco] {len(registros)} avaliação(ões) gravada(s) em avaliacoes_ia")


def _gravar_json(avaliacoes: list[dict]) -> None:
    _SAIDA.mkdir(parents=True, exist_ok=True)
    data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    caminho = _SAIDA / f"{data_hoje}.json"

    aprovadas = [a for a in avaliacoes if a["veredito"]]
    reprovadas = [a for a in avaliacoes if not a["veredito"]]

    saida = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "threshold": THRESHOLD,
        "total_avaliadas": len(avaliacoes),
        "aprovadas": [
            {
                "empresa_id": a["empresa_id"],
                "nome": a["nome"],
                "pontuacao": a["pontuacao"],
                "sinais_ativos": a["sinais_ativos"],
            }
            for a in sorted(aprovadas, key=lambda x: x["pontuacao"], reverse=True)
        ],
        "reprovadas": [
            {
                "empresa_id": a["empresa_id"],
                "nome": a["nome"],
                "pontuacao": a["pontuacao"],
                "motivo": "pontuação abaixo do threshold" if a["pontuacao"] > 0 else "nenhum sinal de IA encontrado",
            }
            for a in sorted(reprovadas, key=lambda x: x["pontuacao"], reverse=True)
        ],
    }

    caminho.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[json] vereditos salvos em {caminho}")


def filtrar(gravar_banco: bool = True, filtrar_nome: str | None = None) -> list[dict]:
    """Lê sinais do Supabase, avalia cada empresa e grava resultados."""
    print("[info] carregando dados do Supabase...")
    mapa_nomes, sinais = _carregar_dados()
    if filtrar_nome:
        mapa_nomes = {eid: n for eid, n in mapa_nomes.items() if n.strip().lower() == filtrar_nome.strip().lower()}
    agrupado = _agrupar_por_empresa(sinais)

    avaliacoes: list[dict] = []
    for empresa_id, nome in sorted(mapa_nomes.items()):
        sinais_empresa = agrupado.get(empresa_id, [])
        resultado = _avaliar_empresa(empresa_id, nome, sinais_empresa)
        avaliacoes.append(resultado)

        status = "✅ APROVADA" if resultado["veredito"] else "❌ reprovada"
        print(f"  [{resultado['pontuacao']:>2}pts] {nome:<30} {status}")

    aprovadas = [a for a in avaliacoes if a["veredito"]]
    print(f"\n[resumo] {len(aprovadas)}/{len(avaliacoes)} empresa(s) aprovada(s) (threshold={THRESHOLD})")

    if gravar_banco:
        _gravar_supabase(avaliacoes)

    _gravar_json(avaliacoes)

    return aprovadas


if __name__ == "__main__":
    filtrar()
