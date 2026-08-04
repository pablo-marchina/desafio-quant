"""Limpeza e compactacao de textos de evidencia antes de chamadas LLM."""

import re
import unicodedata


MAX_EVIDENCE_CHARS_FOR_EXTRACTION = 2800
MAX_BOILERPLATE_LINE_CHARS = 160
MAX_LOW_SIGNAL_LINES = 4
_BOILERPLATE_LINE_HINTS = (
    "all rights reserved",
    "assine",
    "buscar",
    "cadastre",
    "compartilhe",
    "connect",
    "cookie",
    "copa do mundo fifa",
    "copyright",
    "entrar",
    "facebook",
    "forgotten password",
    "home",
    "instagram",
    "linkedin",
    "login",
    "menu",
    "newsletter",
    "nao encontrou",
    "politica de privacidade",
    "privacy policy",
    "publicidade",
    "related posts",
    "similar jobs",
    "termos de servico",
    "termos de uso",
    "terms of service",
    "twitter",
    "welcome back",
)
_CONTENT_LINE_HINTS = (
    "aceleradora",
    "agente",
    "agentes",
    "api",
    "arquitetura",
    "automacao",
    "bert",
    "bertimbau",
    "busca semantica",
    "chatbot",
    "cliente",
    "clientes",
    "computer vision",
    "copilot",
    "dados",
    "deep learning",
    "deeptech",
    "deploy",
    "documentos",
    "evidencia",
    "extracao",
    "fine tuning",
    "fundada",
    "fundador",
    "fundadores",
    "funding",
    "gpu",
    "ia",
    "ia generativa",
    "inferencia",
    "inteligencia artificial",
    "large language model",
    "llm",
    "machine learning",
    "modelo",
    "modelos",
    "nlp",
    "nlp",
    "openai",
    "piloto",
    "plataforma",
    "producao",
    "produto",
    "proprietario",
    "proprietarios",
    "rag",
    "receita",
    "rodada",
    "scale",
    "soberania",
    "startup",
    "treina",
    "treinamento",
    "visao computacional",
)
_LOW_SIGNAL_PREFIXES = (
    "anterior",
    "artigos relacionados",
    "benefits",
    "browse",
    "comunidade startups",
    "conheca as empresas",
    "contato",
    "eventos",
    "espacos disponiveis",
    "f.a.q",
    "infraestrutura",
    "ir para o conteudo",
    "job seekers",
    "links rapidos",
    "mais noticias",
    "mais lidas",
    "next post",
    "posts recentes",
    "similar jobs",
    "skip to content",
    "sobre",
    "trabalhe conosco",
    "veja tambem",
)


def _normalize_boilerplate_key(text: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _is_boilerplate_line(line: str) -> bool:
    normalized = _normalize_boilerplate_key(line)
    if not normalized:
        return True
    if any(hint in normalized for hint in _CONTENT_LINE_HINTS):
        if len(normalized) > 40:
            return False
    if normalized in {"x", "+", "-", "|", "sim", "nao"}:
        return True
    if normalized.startswith(_LOW_SIGNAL_PREFIXES):
        return True
    return len(normalized) <= MAX_BOILERPLATE_LINE_CHARS and any(
        hint in normalized for hint in _BOILERPLATE_LINE_HINTS
    )


def _line_score(line: str, index: int) -> int:
    normalized = _normalize_boilerplate_key(line)
    score = 0
    if normalized.startswith("[evidence_id="):
        score += 100
    if index <= 2:
        score += 12
    score += sum(10 for hint in _CONTENT_LINE_HINTS if hint in normalized)
    if re.search(r"\b(20\d{2}|r\$|usd|us\$|\d+[,.]?\d*\s*(milhoes|mil|m\+|k))\b", normalized):
        score += 8
    if len(normalized) >= 80:
        score += 4
    if len(normalized) <= 24 and score < 15:
        score -= 6
    return score


def _strip_evidence_boilerplate(text: str) -> str:
    """Remove navegacao/rodape, repeticoes obvias e linhas de baixissimo sinal."""
    seen: set[str] = set()
    candidates: list[tuple[int, int, str]] = []
    low_signal_kept = 0
    for index, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        key = _normalize_boilerplate_key(line)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        if _is_boilerplate_line(line):
            continue
        score = _line_score(line, index)
        if score <= 0:
            if low_signal_kept >= MAX_LOW_SIGNAL_LINES:
                continue
            low_signal_kept += 1
        candidates.append((index, score, line))

    high_signal = [item for item in candidates if item[1] > 0]
    low_signal = [item for item in candidates if item[1] <= 0]
    selected = high_signal + low_signal[:MAX_LOW_SIGNAL_LINES]
    selected.sort(key=lambda item: item[0])
    return "\n".join(line for _, _, line in selected)


def compact_evidence_text(text: str) -> str:
    """Colapsa whitespace e limita tamanho do texto de evidencia.

    Boilerplate de navegacao infla o texto com muitos espacos e quebras de
    linha. Compactar reduz tokens sem remover palavras do corpo, e o limite por
    evidencia evita que varias paginas longas estourem o timeout do LLM.
    """
    stripped = _strip_evidence_boilerplate(text)
    compacted = re.sub(r"\s+", " ", stripped).strip()
    return compacted[:MAX_EVIDENCE_CHARS_FOR_EXTRACTION]
