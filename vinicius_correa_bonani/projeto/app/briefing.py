"""Briefing — relatório executivo final, com uma passada de reflection.

`redigir` gera o rascunho a partir de tudo que o pipeline produziu (perfil,
classificação, recomendação, score) citando as fontes do `contexto_rag`. Em seguida,
`revisar` faz uma passada de reflection: um LLM confere o rascunho contra as fontes e
corrige o resíduo que o prompt sozinho deixa passar — número/spec sem lastro e citação
cuja URL não sustenta a afirmação. Linguagem de negócio, não catálogo de produto.

`numeros_sem_fonte` é uma rede de segurança determinística (sem LLM): sinaliza métricas
de melhoria (`%`, `×`) no texto final cujo número não aparece nas fontes — vira aviso de
observabilidade e é testável. LLM via app.llm (provedor selecionável).
"""

import re

from app.config import settings
from app.llm import chat
from app.state import RadarState

_INSTRUCAO = (
    "Você redige um briefing executivo (markdown) para o gerente de Startups & VCs da NVIDIA "
    "sobre uma startup, apoiando a abordagem comercial/técnica do programa NVIDIA Inception.\n"
    "Seja conciso e use linguagem de negócio (custo, latência, defensibilidade), não catálogo de produto.\n"
    "Estruture: visão geral da empresa, diagnóstico AI-native, tecnologias NVIDIA recomendadas com o "
    "porquê, prioridade/próxima ação, e o score.\n"
    "REGRA DE RIGOR (crítica): use SOMENTE informação presente no PERFIL, na RECOMENDAÇÃO ou no "
    "CONTEXTO NVIDIA. TODO número, percentual ou métrica — ex.: 'reduz latência 50%', 'corta custo 30%', "
    "'3x throughput', latência em ms, custo por token, benchmarks, nomes de chip/modelo — só pode aparecer "
    "se estiver LITERALMENTE em uma das fontes. Caso contrário é PROIBIDO citá-lo: escreva o benefício de "
    "forma qualitativa (ex.: 'menor latência de inferência', 'redução de custo de serving') ou use "
    "'não quantificado'. Nunca estime, arredonde nem invente ganhos percentuais. Ao citar uma spec real, "
    "inclua a URL da fonte."
)

_INSTRUCAO_REVISAO = (
    "Você revisa o rigor factual de um briefing. O BRIEFING e o MATERIAL PERMITIDO estão AMBOS "
    "fornecidos abaixo (delimitados) — o conteúdo JÁ ESTÁ presente; NÃO peça nada e NÃO faça perguntas. "
    "O MATERIAL PERMITIDO inclui o PERFIL da empresa, a RECOMENDAÇÃO, o SCORE (calculado pelo pipeline) "
    "e o CONTEXTO NVIDIA — TUDO isso é fonte VÁLIDA. Em particular, o score e o funding do perfil são "
    "legítimos: NÃO os marque como 'não quantificado' se aparecerem no material.\n"
    "Devolva SEMPRE o briefing revisado em markdown, preservando estrutura, seções e conteúdo — "
    "altere APENAS o que violar as duas regras:\n"
    "1) Todo número, percentual ou métrica (ex.: '50%', '10×', '3x', latência em ms, custo) que NÃO "
    "apareça no MATERIAL PERMITIDO deve ser removido e reescrito de forma qualitativa (ex.: 'menor "
    "latência') ou marcado como 'não quantificado'. NÃO invente nem estime.\n"
    "2) Toda citação (URL) cujo conteúdo no MATERIAL NÃO sustente a afirmação ao lado deve ter a citação "
    "removida (mantenha a afirmação, tire a fonte incorreta).\n"
    "Não adicione informação nova. Sua resposta deve ser o briefing revisado inteiro, nada mais."
)

# Métricas de MELHORIA: percentuais e multiplicadores. Escopo restrito de propósito —
# não pega score (6.67), data (16 Jul) nem funding (R$ 700 mi), evitando falso-positivo.
_PADRAO_METRICA = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|×|[xX]\b)")


def redigir(state: RadarState) -> str:
    dados = state.dados_estruturados.model_dump_json(indent=2) if state.dados_estruturados else "{}"
    rec = state.recomendacao.model_dump_json(indent=2) if state.recomendacao else "{}"
    score = state.score.model_dump_json() if state.score else "{}"
    contexto = "\n".join(state.contexto_rag) or "(sem contexto)"
    prompt = (
        f"{_INSTRUCAO}\n\n"
        f"EMPRESA:\n{dados}\n\n"
        f"CLASSIFICAÇÃO: {state.classificacao}\n\n"
        f"RECOMENDAÇÃO:\n{rec}\n\n"
        f"SCORE:\n{score}\n\n"
        f"CONTEXTO NVIDIA (fontes para citar):\n{contexto}"
    )
    resp = chat(temperature=0.3).invoke(prompt)
    return getattr(resp, "content", str(resp))


def _material_permitido(state: RadarState) -> list[str]:
    """Tudo que o briefing PODE citar como fato: perfil da empresa, recomendação e score
    (valores legítimos do próprio pipeline) + o contexto NVIDIA recuperado. Sem isso, a
    reflection apagaria score/funding por não estarem nas docs da NVIDIA (bug do over-strip)."""
    mat: list[str] = []
    if state.dados_estruturados:
        mat.append("PERFIL DA EMPRESA:\n" + state.dados_estruturados.model_dump_json(indent=2))
    if state.recomendacao:
        mat.append("RECOMENDAÇÃO:\n" + state.recomendacao.model_dump_json(indent=2))
    if state.score:
        mat.append("SCORE (calculado pelo pipeline):\n" + state.score.model_dump_json())
    mat.extend(state.contexto_rag)
    return mat


def revisar(rascunho: str, material: list[str]) -> str:
    """Reflection: revisa o rascunho contra o material permitido, tirando número sem lastro
    e citação incoerente. Preserva o resto do texto."""
    fontes = "\n\n".join(material) or "(sem material)"
    prompt = (
        f"{_INSTRUCAO_REVISAO}\n\n"
        f"=== MATERIAL PERMITIDO ===\n{fontes}\n\n"
        f"=== BRIEFING A REVISAR ===\n{rascunho}\n"
        f"=== FIM DO BRIEFING ===\n\n"
        f"Devolva agora o briefing revisado inteiro:"
    )
    resp = chat(temperature=0.0).invoke(prompt)
    return getattr(resp, "content", str(resp))


def _revisao_valida(revisado: str, rascunho: str) -> bool:
    """Uma revisão degenerada (vazia, ou muito mais curta que o rascunho — ex.: o LLM
    "pediu o briefing" em vez de revisar) NÃO deve substituir o rascunho bom."""
    return bool(revisado.strip()) and len(revisado.strip()) >= 0.5 * len(rascunho.strip())


def numeros_sem_fonte(texto: str, material: list[str]) -> list[str]:
    """Métricas de melhoria (%, ×) no texto cujo número não aparece no material permitido.
    Heurística determinística (rede de segurança/observabilidade), não verdade absoluta."""
    fontes = " ".join(material)
    fora = []
    for m in _PADRAO_METRICA.finditer(texto):
        token = m.group(0)
        num = re.search(r"\d+(?:[.,]\d+)?", token).group(0)
        if num not in fontes:
            fora.append(token.strip())
    return fora


def briefing(state: RadarState) -> dict:
    rascunho = redigir(state)
    material = _material_permitido(state)  # perfil + recomendação + score + contexto NVIDIA

    # reflection: reforço opcional; se falhar OU devolver saída degenerada, mantém o
    # rascunho (não derruba o pipeline nem deixa a revisão apagar o briefing bom).
    if settings.briefing_reflection and settings.llm_api_key and rascunho.strip():
        try:
            revisado = revisar(rascunho, material)
            if _revisao_valida(revisado, rascunho):
                rascunho = revisado
            else:
                print("[briefing] reflection devolveu saída degenerada; mantendo o rascunho.")
        except Exception as e:  # noqa: BLE001 — degradar é intencional
            print(f"[briefing] reflection falhou ({e}); usando o rascunho.")

    residuo = numeros_sem_fonte(rascunho, material)
    if residuo:
        print(f"[briefing] {len(residuo)} métrica(s) sem fonte após reflection: {residuo}")

    return {"briefing": rascunho}
