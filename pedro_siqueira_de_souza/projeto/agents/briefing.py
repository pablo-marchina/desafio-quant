"""Briefing Agent — nona e última estação do pipeline.

Junta tudo que as estações anteriores produziram sobre cada startup —
identidade, classificação de maturidade de IA, validação de evidências e a
stack NVIDIA recomendada (com citações) — num RELATÓRIO EXECUTIVO em markdown,
pronto para o Gerente de Startups & VCs usar na abordagem comercial.

Por que DETERMINÍSTICO (sem LLM) e não gerado por modelo:
  - O briefing é o ARTEFATO FINAL e precisa ser FIEL: cada número, rótulo e
    citação tem de bater com o que o pipeline apurou. Gerar o relatório por LLM
    abriria espaço para alucinação justo no produto entregue — risco que não se
    justifica aqui. Montamos o markdown a partir dos dados estruturados.
  - Sinalizar SEMPRE o nível de confiança é exigência do projeto:
    o briefing consolida os sinais de evidência (textual e validação de
    fontes) num só lugar.
  Uma camada de NARRATIVA via LLM (resumo executivo em prosa por cima dos
  fatos) é o aprimoramento natural seguinte — análogo à versão LLM do
  Recommendation Agent.
"""
from loguru import logger
from pydantic import BaseModel

from agents.state import RadarState


class Briefing(BaseModel):
    """Relatório executivo final de uma startup."""

    name: str
    label: str
    markdown: str


# Quantos produtos citar na narrativa do briefing (curto de propósito).
_MAX_PRODUTOS_BRIEFING = 2


def _cap(texto: str) -> str:
    """Primeira letra maiúscula (descrição/teses vêm em minúscula do dado bruto)."""
    t = texto.strip()
    return t[:1].upper() + t[1:] if t else t


def _render_briefing(rec: dict, validated: dict | None) -> str:
    """Monta um briefing CURTO de recomendação (no máximo 2 parágrafos).

    Mudança de design: o briefing deixou de ser um relatório longo com várias
    seções (a página Qualificadas já mostra "Sobre a empresa" e "Produtos
    compatíveis" em separado). Aqui é uma NARRATIVA enxuta para a NVIDIA:
      - Parágrafo 1: quem é a empresa + diagnóstico de maturidade de IA.
      - Parágrafo 2: a recomendação de produtos NVIDIA e por que ajudam a crescer.
    Continua DETERMINÍSTICO (montado dos dados estruturados, sem LLM e sem
    alucinação) e usa **negrito** leve — o frontend renderiza formatado.

    `rec` é um StartupRecommendation serializado; `validated` é o
    ValidatedStartup correspondente (ou None).
    """
    name = rec["name"]
    label = rec["label"]

    # --- Parágrafo 1: quem é + diagnóstico ---
    p1 = f"**{name}**"
    if validated is not None:
        startup = validated["classified"]["startup"]
        setor = startup.get("sector")
        estagio = startup.get("stage")
        if setor:
            p1 += f" atua em {setor}"
        if estagio:
            p1 += f" ({estagio})"
        p1 += f" e é classificada como **{label}**"
        p1 += f" (confiança {validated['classified']['confidence']})."
        if startup.get("description"):
            p1 += f" {_cap(startup['description'].rstrip('.'))}."
    else:
        p1 += f" é classificada como **{label}**."

    # --- Parágrafo 2: recomendação NVIDIA (curta) ---
    techs = rec.get("technologies", [])[:_MAX_PRODUTOS_BRIEFING]
    if techs:
        nomes = " e ".join(f"**{t['tech']}**" for t in techs)
        p2 = f"Recomendação NVIDIA: {nomes}. "
        p2 += " ".join(_cap(t["growth"].rstrip(".")) + "."
                       for t in techs if t.get("growth"))
        for nota in rec.get("notes", []):
            p2 += f" {_cap(nota.rstrip('.'))}."
    else:
        p2 = ("Nenhum produto NVIDIA aderente ao perfil atual foi identificado "
              "— recomenda-se reavaliar após enriquecer os dados da empresa.")

    return f"{p1}\n\n{p2}"


def briefing_node(state: RadarState) -> dict:
    """Nó final do grafo: gera o relatório executivo por startup."""
    recomendacoes = state.get("recommendations", [])
    validadas = state.get("validated_startups", [])
    # Junta o validated (identidade/classificação) à recomendação, por nome.
    val_por_nome = {
        v["classified"]["startup"]["name"]: v for v in validadas
    }

    briefings: list[Briefing] = []
    for rec in recomendacoes:
        validated = val_por_nome.get(rec["name"])
        markdown = _render_briefing(rec, validated)
        briefings.append(Briefing(name=rec["name"], label=rec["label"], markdown=markdown))

    logger.info("briefing: {} relatórios gerados", len(briefings))
    return {
        "briefings": [b.model_dump() for b in briefings],
        "messages": [
            ("ai", f"[briefing] {len(briefings)} relatórios executivos gerados")
        ],
    }
