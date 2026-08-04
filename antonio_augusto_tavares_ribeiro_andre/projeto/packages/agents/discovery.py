"""Descoberta da coorte por linguagem natural (F3.10/F5.12) — o motor do chat.

Traduz uma pergunta em PT-BR ("quais startups são mais propensas a precisar de NIM?", "healthtech
AI-native com gap de inferência", "as mais maduras") nos **filtros estruturados** que a lista da
coorte já entende (`apps/api/companies.list_companies`: setor · classe · AIMI mínimo · tech usada ·
**tech NVIDIA recomendada**), ranqueados por Inception Priority.

**Insight central:** "suscetível à tecnologia X" = "o recommender (F4) **prescreveu** X" = "tem o
gap que X preenche". Então filtrar por **tech NVIDIA recomendada** já captura a susceptibilidade — o
pipeline fez o mapeamento gap→tech. Por isso o chat não precisa de um índice semântico próprio: a
descoberta vira *parsing de intenção → filtro*. A "família de inferência" (graduar da API → stack
otimizada) é ancorada pelo **NIM** (a tech que a regra F4.1 dispara em todo gap de Technical
Optimization), então intenções de graduação/otimização mapeiam pra `nvidia_tech=NIM`.

Determinístico e offline por design (espinha-verde): é parsing de palavra-chave sobre o vocabulário
controlado (`tech_vocab`, F5.11), reprodutível e sem rede. Um extrator LLM (Nemotron) pode entrar
depois atrás de flag para NL mais livre — o contrato (`CohortQuery`) já isola isso.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from packages.schemas.tech_vocab import normalize_tech

# Tokenização Unicode (palavras) compartilhada pelo parser e pelo resíduo semântico (F3.10).
_TOKEN = re.compile(r"\w+", re.UNICODE)

# Termo (minúsculo) → tag NVIDIA canônica recomendada. Ordem importa: termos compostos
# ("nemo retriever") antes dos curtos ("nemo") p/ o match mais específico vencer.
_NVIDIA_TERMS: tuple[tuple[str, str], ...] = (
    ("nemo retriever", "NeMo Retriever"),
    ("tensorrt-llm", "TensorRT-LLM"),
    ("tensorrt", "TensorRT-LLM"),
    ("tensor rt", "TensorRT-LLM"),
    ("trt-llm", "TensorRT-LLM"),
    ("triton", "Triton"),
    ("nim", "NIM"),
    ("rapids", "RAPIDS"),
    ("cudf", "cuDF"),
    ("cuml", "cuML"),
    ("guardrails", "NeMo Guardrails"),
    ("riva", "Riva"),
    ("clara", "Clara"),
    ("monai", "MONAI"),
    ("morpheus", "Morpheus"),
    ("ai enterprise", "AI Enterprise"),
    ("nemo", "NeMo"),
)

# Intenção de graduação/otimização de inferência → o gap que o NIM ancora (proxy de
# graduation-ready: AI-native com Technical Optimization baixo).
_INFERENCE_INTENT: tuple[str, ...] = (
    "inferênc", "inferenc", "serving", "otimiz", "graduar", "graduaç", "graduac",
    "graduation", "wrapper", "self-host", "self host", "self-hosted",
)

# Termo (minúsculo) → classe (§5.1). Composto antes do simples.
_CLASS_TERMS: tuple[tuple[str, str], ...] = (
    ("ai-native", "AI-native"),
    ("ai native", "AI-native"),
    ("ai-nativa", "AI-native"),
    ("nativa de ia", "AI-native"),
    ("ai-enabled", "AI-enabled"),
    ("ai enabled", "AI-enabled"),
    ("habilitada por ia", "AI-enabled"),
    ("non-ai", "non-AI"),
    ("non ai", "non-AI"),
    ("não-ia", "non-AI"),
    ("nao-ia", "non-AI"),
)

# "AIMI ≥ 40", "AIMI acima de 40", "AIMI 40"
_AIMI_RE = re.compile(r"aimi\s*(?:>=|≥|acima de|maior que|a partir de|de|>)?\s*(\d{1,3})")
# "maduras"/"maturidade alta" sem número → piso convencional.
_MADURA_RE = re.compile(r"madur")
_MADURA_MIN_AIMI = 50


class CohortQuery(BaseModel):
    """Filtros estruturados extraídos da pergunta (espelham `list_companies`)."""

    setor: str | None = None
    classificacao: str | None = None
    min_aimi: int | None = None
    nvidia_tech: str | None = Field(default=None, description="Tag NVIDIA recomendada (F5.11).")
    tech: str | None = Field(default=None, description="Tag que a startup usa.")
    entendido: str = Field(default="", description="Eco legível do que foi entendido da pergunta.")


def _first_match(low: str, pairs: tuple[tuple[str, str], ...]) -> str | None:
    """Primeira tag cujo termo aparece no texto (ordem = especificidade)."""
    for term, tag in pairs:
        if term in low:
            return tag
    return None


def parse_query(text: str) -> CohortQuery:
    """Pergunta em PT-BR → `CohortQuery` (determinístico, offline).

    Reconhece: tech NVIDIA recomendada (incl. intenção de graduação → NIM), classe, e um piso de
    AIMI ("AIMI ≥ N" / "maduras"). O que não casar fica `None` (sem filtro). O `entendido` resume,
    em texto, o que o parser captou — o chat o devolve p/ o usuário ver como foi interpretado.
    """
    low = text.lower()
    bits: list[str] = []

    nvidia = _first_match(low, _NVIDIA_TERMS)
    if nvidia is None and any(t in low for t in _INFERENCE_INTENT):
        nvidia = "NIM"
        bits.append("gap de inferência (candidata a NIM/TensorRT/Triton)")
    elif nvidia is not None:
        bits.append(f"recomenda {nvidia}")

    classificacao = _first_match(low, _CLASS_TERMS)
    if classificacao:
        bits.append(classificacao)

    min_aimi: int | None = None
    if m := _AIMI_RE.search(low):
        min_aimi = min(int(m.group(1)), 100)
        bits.append(f"AIMI ≥ {min_aimi}")
    elif _MADURA_RE.search(low):
        min_aimi = _MADURA_MIN_AIMI
        bits.append(f"maduras (AIMI ≥ {min_aimi})")

    return CohortQuery(
        classificacao=classificacao,
        min_aimi=min_aimi,
        nvidia_tech=nvidia,
        entendido="; ".join(bits) or "toda a coorte, por prioridade de outreach",
    )


# Palavras-função/genéricas das perguntas da coorte que **não** carregam intenção semântica
# (conectivos + os verbos/substantivos de "pergunta de descoberta"). Tudo isto é descartado ao
# medir se sobra texto livre — só o que NÃO está aqui (nem é filtro nem stem de inferência) conta
# como sinal semântico (ex.: "fraude", "agro", "visão computacional").
_QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        "de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "um", "uma", "que", "com",
        "sem", "por", "para", "pra", "quais", "qual", "quem", "sao", "são", "tem", "têm", "ter",
        "mais", "menos", "muito", "startup", "startups", "empresa", "empresas", "negocio",
        "negocios", "candidata", "candidatas", "candidato", "candidatos", "propensa", "propensas",
        "propenso", "precisa", "precisam", "precisar", "precisando", "beneficia", "beneficiaria",
        "beneficiariam", "gap", "gaps", "me", "mostra", "mostre", "lista", "liste", "quero", "ver",
        "sobre", "na", "no", "nas", "nos", "ao", "aos", "todas", "todos", "toda", "todo", "essa",
        "esse", "essas", "esses", "minha", "coorte", "ia", "ai",
        # comparadores/qualificadores de maturidade (o número e "aimi"/"madur" já caem à parte)
        "acima", "abaixo", "maior", "menor", "igual", "partir", "nivel", "niveis", "maturidade",
        "alta", "alto", "baixa", "baixo", "media", "média", "score",
    }
)

# Tokens das grafias de filtro (tech NVIDIA + classe): descartados ao medir o resíduo, pois já
# viraram filtro estruturado. Flatten das surfaces (`_NVIDIA_TERMS`/`_CLASS_TERMS`) em palavras.
_FILTER_TOKENS: frozenset[str] = frozenset(
    tok for term, _ in (_NVIDIA_TERMS + _CLASS_TERMS) for tok in _TOKEN.findall(term)
)


def _is_content_token(tok: str) -> bool:
    """True se o token carrega sinal semântico (não é filtro/stopword/intenção/número/curto)."""
    if len(tok) < 3 or tok.isdigit():
        return False
    if tok in _QUERY_STOPWORDS or tok in _FILTER_TOKENS:
        return False
    if tok.startswith("aimi") or tok.startswith("madur"):
        return False
    return not any(stem in tok for stem in _INFERENCE_INTENT)


def residual_query(text: str) -> str:
    """Texto livre que sobra depois de remover tudo que o parser de filtro já consome.

    Tokeniza a pergunta e descarta: grafias de tech/classe (viram filtro), os stems de intenção de
    inferência (`_INFERENCE_INTENT`), o vocabulário de AIMI/maturidade, números, e as
    palavras-função genéricas das perguntas da coorte (`_QUERY_STOPWORDS`). O que sobra é o **sinal
    semântico** — setor/domínio em texto livre que o vocabulário controlado não cobre (ex.:
    "fraude", "agro", "visão computacional"). Vazio ⇒ a pergunta é 100% filtro estruturado e o chat
    mantém a ordem por Inception Priority; não-vazio ⇒ há o que ranquear por similaridade (F3.10).
    """
    tokens = _TOKEN.findall(unicodedata.normalize("NFC", text).lower())
    return " ".join(tok for tok in tokens if _is_content_token(tok))


def summarize(query: CohortQuery, count: int) -> str:
    """Frase de resposta do chat: o que entendeu + quantas achou (ordem = Inception Priority)."""
    plural = "startup" if count == 1 else "startups"
    return (
        f"Encontrei {count} {plural} — {query.entendido} — "
        f"ordenadas por Inception Priority (upside NVIDIA × potencial)."
    )


__all__ = ["CohortQuery", "parse_query", "residual_query", "summarize", "normalize_tech"]
