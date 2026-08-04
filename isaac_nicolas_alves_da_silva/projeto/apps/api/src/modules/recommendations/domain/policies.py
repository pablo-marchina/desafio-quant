"""Politica de match determinístico entre perfil de startup e catalogo NVIDIA.

Score composto (V4, passo 3): substitui o ratio simples de keywords por uma
formula ponderada em 5 dimensoes — alinhamento de workload (35%), evidencia
concreta (25%), maturidade da startup (15%), prior de keywords (15%) e
viabilidade de implementacao (10%).

Nova confianca (V4, passo 3): combina qualidade da fonte (25%), clareza do
sinal de keywords (25%), proximidade de workload (20%), profundidade de
evidencias (20%) e sinal operacional (10%).

Nivel e faltando (V4, passo 5): cada recomendacao recebe um nivel
(forte/moderada/exploratoria) derivado do score + confianca, mais uma lista
de sinais ausentes que elevariam ao nivel superior.

Todas as funcoes sao puras, sem rede, sem banco, cobertas pela suite
existente.
"""

import re
from dataclasses import dataclass, field
from uuid import UUID

MIN_MATCHED_KEYWORDS = 2
MIN_MATCH_SCORE = 0.20
AI_NATIVE_MATURITY_BOOST = 0.15

# Se o workload da startup tem alta afinidade com a tecnologia (>= limiar),
# admite a recomendacao com apenas 1 keyword — o sinal de workload e
# suficientemente forte para compensar a escassez de keywords literais.
WORKLOAD_ADMISSION_THRESHOLD = 0.60

# Limiares para classificar o nivel de cada recomendacao.
# Forte: fit claro E qualidade de evidencia boa.
# Moderada: algum sinal de relevancia E alguma evidencia de qualidade minima.
# Exploratoria: tudo abaixo, mas ainda acima do MIN_MATCH_SCORE.
NIVEL_FORTE_SCORE = 0.60
NIVEL_FORTE_CONFIDENCE = 0.55
NIVEL_MODERADA_SCORE = 0.38
NIVEL_MODERADA_CONFIDENCE = 0.25

NIVEL_FORTE = "forte"
NIVEL_MODERADA = "moderada"
NIVEL_EXPLORATORIA = "exploratoria"
# Alta relevancia (score) mas confianca baixa: merece qualificacao prioritaria
# em vez de ser descartada junto com hipoteses fracas.  Relevancia e confianca
# sao eixos independentes — score alto com poucas evidencias e' sinal a
# investigar, nao sinal a descartar.
NIVEL_HIPOTESE = "hipotese_prioritaria"

# Limiares para a hipotese_prioritaria: score forte mas confianca insuficiente.
NIVEL_HIPOTESE_SCORE = NIVEL_FORTE_SCORE
NIVEL_HIPOTESE_MAX_CONFIDENCE = NIVEL_FORTE_CONFIDENCE

# Variantes frequentes nas paginas de startups. O catalogo conserva keywords
# canonicas, enquanto a politica reconhece grafias e termos operacionais que
# carregam o mesmo sinal sem depender de LLM. "scale" foi removido do alias de
# "throughput": e prefixo comum de palavras em portugues (ex. "escale") e so
# colidia por causa do match por substring que existia antes do word boundary.
KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "fine tuning": ("fine-tune", "fine tune", "finetune"),
    "training": ("train", "training", "retraining"),
    "model serving": ("serverless", "serving", "model deployment"),
    "inference": ("inference", "inferencing", "serving"),
    "throughput": ("throughput", "scaling"),
    "deployment": ("deployment", "deploy", "production"),
}

# Contextos que invertem o sentido de uma keyword. O caso real que motivou
# isso foi "no training on your data": a palavra "training" aparecia, mas como
# promessa de privacidade, nao como sinal de fine-tuning ou treino de modelo.
KEYWORD_NEGATIVE_PATTERNS: dict[str, tuple[str, ...]] = {
    "training": (
        r"\bno\s+(?:own\s+)?(?:model\s+|data\s+)?training\b",
        r"\bno\s+training\s+on\b",
        r"\bdo(?:es)?\s+not\s+train\b",
        r"\bwill\s+not\s+train\b",
        r"\bnot\s+(?:used\s+to\s+)?train\b",
        r"\bwithout\s+(?:own\s+|model\s+)?training\b",
        r"\bnever\s+train\b",
    ),
    "fine tuning": (
        r"\bno\s+fine[-\s]?tuning\b",
        r"\bwithout\s+fine[-\s]?tuning\b",
        r"\bnot\s+fine[-\s]?tun(?:e|ing)\b",
    ),
    "gpu": (
        r"\bno\s+(?:own\s+)?gpu\b",
        r"\bwithout\s+(?:own\s+)?gpu\b",
        r"\bno\s+own\s+gpu\s+infrastructure\b",
    ),
    "infrastructure": (
        r"\bno\s+own\s+gpu\s+infrastructure\b",
        r"\bwithout\s+own\s+infrastructure\b",
    ),
}

TECHNICAL_SOURCE_HINTS = (
    "docs",
    "documentation",
    "api",
    "developer",
    "developers",
    "github.com",
    "gitlab.com",
    "gupy.io",
    "greenhouse.io",
    "lever.co",
    "changelog",
    "engineering",
    "architecture",
    "sdk",
)

INDEPENDENT_SOURCE_HINTS = (
    "techcrunch.com",
    "startups.com.br",
    "crunchbase.com",
    "linkedin.com",
    "distrito",
    "latitud",
    "abstartups",
    "100openstartups",
    "endeavor",
    "exame.com",
    "valor.globo.com",
)

TECHNICAL_CLAIM_TERMS = (
    "fine tuning",
    "fine-tune",
    "training",
    "inference",
    "model serving",
    "deployment",
    "kubernetes",
    "pytorch",
    "onnx",
    "cuda",
    "triton",
    "nvidia",
    "gpu",
    "embeddings",
    "rag",
    "retrieval",
    "semantic search",
)

OPERATIONAL_CLAIM_TERMS = (
    "production",
    "customers",
    "customer",
    "case study",
    "trusted by",
    "enterprise",
    "scale",
    "funding",
    "series",
    "clientes",
    "cliente",
    "producao",
    "produção",
    "escala",
)

# Conversao de deployment_stage para score de maturidade (0-1).
_MATURITY_SCORE: dict[str, float] = {
    "research": 0.25,
    "mvp": 0.50,
    "pilot": 0.65,
    "production": 0.85,
    "scale": 1.00,
    "unknown": 0.50,
}

# Matriz de compatibilidade (gpu_need, tech_complexity) -> viabilidade.
_VIABILITY: dict[tuple[str, str], float] = {
    ("high",    "high"):   0.90,
    ("high",    "medium"): 0.80,
    ("high",    "low"):    0.70,
    ("medium",  "high"):   0.50,
    ("medium",  "medium"): 0.85,
    ("medium",  "low"):    0.80,
    ("low",     "high"):   0.20,
    ("low",     "medium"): 0.55,
    ("low",     "low"):    0.90,
    ("unknown", "high"):   0.50,
    ("unknown", "medium"): 0.60,
    ("unknown", "low"):    0.65,
}


def _contains_term(text: str, term: str) -> bool:
    """Verifica presenca de ``term`` em ``text`` respeitando word boundary.

    Substring puro (``term in text``) gera falsos positivos linguisticos: a
    palavra em ingles "agent" bate dentro de "agentes" (portugues), "scale"
    bate dentro de "escale". ``\\b`` exige que o caracter antes/depois do termo
    nao seja alfanumerico, eliminando esses casos sem deixar de casar termos
    com espaco ou hifen internos (ex. "fine tuning", "fine-tune").
    """

    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _contains_supported_term(text: str, keyword: str, term: str) -> tuple[bool, bool]:
    """Retorna (hit_positivo, hit_bloqueado_por_contexto_negativo)."""

    blocked = False
    for match in re.finditer(rf"\b{re.escape(term)}\b", text):
        window_start = max(0, match.start() - 80)
        window_end = min(len(text), match.end() + 80)
        window = text[window_start:window_end]
        if any(
            re.search(pattern, window)
            for pattern in KEYWORD_NEGATIVE_PATTERNS.get(keyword, ())
        ):
            blocked = True
            continue
        return True, blocked
    return False, blocked


def _keyword_match_state(text: str, keyword: str) -> tuple[bool, bool]:
    """Avalia a keyword canonica e aliases, preservando contexto negativo."""

    hit = False
    blocked = False
    for term in (keyword, *KEYWORD_ALIASES.get(keyword, ())):
        term_hit, term_blocked = _contains_supported_term(text, keyword, term)
        hit = hit or term_hit
        blocked = blocked or term_blocked
    return hit, blocked


def _has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


@dataclass(frozen=True)
class StartupAIContext:
    """Contexto de IA da startup no vocabulario deste modulo.

    Subconjunto minimo do StartupAIProfile (modulo startups) necessario para
    o score composto. A traducao e responsabilidade do adapter da camada de
    infraestrutura — policies.py nao importa nada de startups.
    """

    ai_workload_type: str = "unknown"
    deployment_stage: str = "unknown"
    gpu_need: str = "unknown"
    has_operational_signal: bool = False
    profile_strength: float = 0.0
    secondary_workloads: tuple[str, ...] = ()


@dataclass(frozen=True)
class TechnologyCandidate:
    """Tecnologia NVIDIA candidata a recomendacao, no vocabulario deste modulo."""

    slug: str
    name: str
    category: str
    use_cases: tuple[str, ...]
    keywords: tuple[str, ...]
    complexity: str = "medium"
    supported_workloads: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceSignal:
    """Texto pesquisavel de uma evidencia, ja normalizado em minusculas."""

    evidence_id: UUID
    text: str
    confidence_score: float = 0.5
    source_url: str | None = None
    evidence_type: str | None = None


@dataclass(frozen=True)
class MatchResult:
    technology: TechnologyCandidate
    score: float
    confidence: float = 0.0
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[UUID, ...] = field(default_factory=tuple)
    signal_origins: tuple[str, ...] = field(default_factory=tuple)
    missing_signals: tuple[str, ...] = field(default_factory=tuple)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    nivel: str = NIVEL_EXPLORATORIA
    faltando: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Componentes do score composto
# ---------------------------------------------------------------------------


def _workload_alignment(
    ai_context: StartupAIContext | None, candidate: TechnologyCandidate
) -> float:
    """Alinhamento entre tipo de workload da startup e perfil da tecnologia.

    Neutral (0.40) quando nao ha informacao de perfil: nem penaliza startups
    sem extracao de perfil completa, nem infla artificialmente.
    """
    if ai_context is None or not candidate.supported_workloads:
        return 0.40
    workloads = [ai_context.ai_workload_type, *ai_context.secondary_workloads]
    scores = [
        candidate.supported_workloads.get(wl, 0.0)
        for wl in workloads
        if wl and wl != "unknown"
    ]
    if not scores:
        return 0.40
    return max(scores)


def _evidence_signal_score(
    *,
    matched_evidence_ids: set[UUID],
    evidence_signals: list[EvidenceSignal],
    profile_strength: float = 0.0,
) -> float:
    """Qualidade e profundidade do sinal de evidencia que suporta o match.

    Sem evidencias: 0.20 (so perfil textual, sinal fraco).
    Com evidencias: media do confidence_score + bonus de profundidade (max +0.15
    por cada evidencia adicional alem da primeira, cap em 0.95).
    """
    # Admitida por perfil (sem evidencia casada por keyword): o perfil FOI
    # extraido de fonte real (field_evidence_ids), entao o field_confidence do
    # perfil vale como sinal de evidencia — escalado, com piso historico 0.20.
    if not matched_evidence_ids:
        return max(0.20, round(0.9 * profile_strength, 2))

    matching = [s for s in evidence_signals if s.evidence_id in matched_evidence_ids]
    if not matching:
        return max(0.20, round(0.9 * profile_strength, 2))

    base = sum(_source_quality(s) for s in matching) / len(matching)
    depth_bonus = min(0.15, 0.05 * (len(matched_evidence_ids) - 1))
    return min(0.95, base + depth_bonus)


def _evidence_type_value(signal: EvidenceSignal) -> float:
    evidence_type = (signal.evidence_type or "").lower()
    if evidence_type == "technical":
        return 0.90
    if evidence_type == "documentation":
        return 0.90
    if evidence_type == "blog":
        return 0.70
    if evidence_type == "news":
        return 0.75
    if evidence_type == "website":
        return 0.60
    if evidence_type:
        return 0.45
    return signal.confidence_score


def _is_technical_evidence(signal: EvidenceSignal) -> bool:
    source = f"{signal.source_url or ''} {signal.evidence_type or ''}".lower()
    return (
        _has_any_term(source, TECHNICAL_SOURCE_HINTS)
        or _has_any_term(signal.text, TECHNICAL_CLAIM_TERMS)
    )


def _is_independent_evidence(signal: EvidenceSignal) -> bool:
    source = f"{signal.source_url or ''} {signal.evidence_type or ''}".lower()
    return (
        "news" in source
        or _has_any_term(source, INDEPENDENT_SOURCE_HINTS)
    )


def _has_operational_evidence(signal: EvidenceSignal) -> bool:
    return _has_any_term(signal.text, OPERATIONAL_CLAIM_TERMS)


def _source_quality(signal: EvidenceSignal) -> float:
    """Qualidade da fonte para recomendacao, nao apenas confianca do scraping."""

    source_value = _evidence_type_value(signal)
    source = f"{signal.source_url or ''} {signal.evidence_type or ''}".lower()

    if _has_any_term(source, TECHNICAL_SOURCE_HINTS):
        source_value = max(source_value, 0.90)
    elif _has_any_term(source, INDEPENDENT_SOURCE_HINTS):
        source_value = max(source_value, 0.75)

    if _is_technical_evidence(signal):
        source_value = min(1.0, source_value + 0.05)
    if _is_independent_evidence(signal):
        source_value = min(1.0, source_value + 0.05)

    blended = 0.60 * signal.confidence_score + 0.40 * source_value
    return min(1.0, max(0.0, blended))


def _confidence_cap(
    *,
    matched_evidence_ids: set[UUID],
    evidence_signals: list[EvidenceSignal],
    ai_context: StartupAIContext | None,
) -> float:
    """Teto de confianca por tipo de evidencia disponivel."""

    if not matched_evidence_ids:
        return 0.45

    matching = [s for s in evidence_signals if s.evidence_id in matched_evidence_ids]
    if not matching:
        return 0.45

    has_technical = any(_is_technical_evidence(s) for s in matching)
    has_independent = any(_is_independent_evidence(s) for s in matching)
    has_operational = any(_has_operational_evidence(s) for s in matching) or (
        ai_context is not None
        and (
            ai_context.deployment_stage in ("production", "scale")
            or ai_context.has_operational_signal
        )
    )

    if has_technical and has_operational:
        return 0.90
    if has_technical and has_independent:
        return 0.82
    if has_independent and len(matching) >= 2:
        return 0.75
    if has_technical:
        return 0.68
    if has_independent:
        return 0.72
    if len(matching) >= 2:
        return 0.65
    return 0.60


def _startup_maturity_score(ai_context: StartupAIContext | None) -> float:
    """Score de maturidade: quanto mais proxima de producao, melhor o fit."""
    if ai_context is None:
        return 0.50
    return _MATURITY_SCORE.get(ai_context.deployment_stage, 0.50)


def _implementation_viability(
    ai_context: StartupAIContext | None, candidate: TechnologyCandidate
) -> float:
    """Compatibilidade entre necessidade de GPU da startup e complexidade da tech.

    Alta necessidade de GPU + tecnologia complexa = fit perfeito.
    Baixa necessidade + tecnologia complexa = risco real de nao conseguir
    implementar ou ver valor.
    """
    if ai_context is None:
        return 0.60
    gpu = ai_context.gpu_need
    complexity = candidate.complexity
    return _VIABILITY.get((gpu, complexity), 0.55)


def _workload_admission_category_allowed(
    ai_context: StartupAIContext | None,
    candidate: TechnologyCandidate,
    *,
    matched_keyword_count: int,
) -> bool:
    """Evita que workload generico admita tecnologias de outra categoria.

    O caminho por workload e deliberadamente mais permissivo que keywords, mas
    ele nao pode transformar "analytics" ou "nlp" em sinal de speech,
    cybersecurity ou healthcare sem evidencias textuais diretas.
    """

    if ai_context is None:
        return False

    workloads = {
        workload
        for workload in (ai_context.ai_workload_type, *ai_context.secondary_workloads)
        if workload and workload != "unknown"
    }
    category = candidate.category

    if category == "speech_ai":
        return "speech" in workloads
    if category == "cybersecurity":
        return bool(workloads & {"cybersecurity", "security"})
    if category == "healthcare_ai":
        return matched_keyword_count > 0 and bool(
            workloads & {"healthcare", "vision"}
        )

    if matched_keyword_count > 0:
        return True

    if "analytics" in workloads:
        return category in {"data_science", "accelerated_computing"}
    if "nlp" in workloads:
        return category in {
            "model_serving",
            "model_training",
            "model_optimization",
            "mlops",
            "ai_platform",
        }
    if "vision" in workloads:
        return category in {
            "computer_vision",
            "model_serving",
            "model_optimization",
            "mlops",
        }
    if "speech" in workloads:
        return category in {"speech_ai", "model_serving", "model_training"}

    return False


def _composite_score(
    *,
    keyword_prior: float,
    workload_aln: float,
    evidence_sig: float,
    startup_mat: float,
    impl_viab: float,
    ai_maturity_level: str | None,
) -> float:
    """Score composto com 5 dimensoes ponderadas.

    ai_native recebe um bonus pequeno (5 p.p.) na dimensao de viabilidade
    de implementacao — empresas que ja constroem AI-first tem mais facilidade
    com tecnologias NVIDIA complexas. Antes o bonus era aplicado no score
    final; agora fica numa dimensao propria para nao distorcer o total.
    """
    if ai_maturity_level == "ai_native":
        impl_viab = min(1.0, impl_viab + AI_NATIVE_MATURITY_BOOST)

    return (
        0.35 * workload_aln
        + 0.25 * evidence_sig
        + 0.15 * startup_mat
        + 0.15 * keyword_prior
        + 0.10 * impl_viab
    )


def _composite_confidence(
    *,
    evidence_signals: list[EvidenceSignal],
    matched_evidence_ids: set[UUID],
    keyword_prior: float,
    workload_aln: float,
    ai_context: StartupAIContext | None,
) -> float:
    """Nova confianca: combina 5 fatores independentes.

    1. source_quality (25%): media do confidence_score das evidencias que
       contribuiram para o match; 0 quando so perfil.
    2. signal_clarity (25%): fracao de keywords do catalogo que bateram.
    3. workload_proximity (20%): reutiliza o workload_alignment.
    4. evidence_depth (20%): proporcao de evidencias independentes (cap em 3).
    5. operational_signal (10%): startup esta em producao/escala ou tem sinal
       de escala reportado.
    """
    # 1. source_quality
    if matched_evidence_ids:
        matching = [s for s in evidence_signals if s.evidence_id in matched_evidence_ids]
        source_quality = (
            sum(_source_quality(s) for s in matching) / len(matching)
            if matching
            else 0.0
        )
    else:
        source_quality = 0.0

    # 2. signal_clarity = keyword_prior
    signal_clarity = keyword_prior

    # 3. workload_proximity
    workload_proximity = workload_aln

    # 4. evidence_depth: 0 evid=0.0, 1=0.33, 2=0.67, 3+=1.0
    n = len(matched_evidence_ids)
    evidence_depth = min(1.0, n / 3.0) if n > 0 else 0.0

    # 5. operational_signal
    if ai_context is not None and (
        ai_context.deployment_stage in ("production", "scale")
        or ai_context.has_operational_signal
    ):
        operational_signal = 1.0
    else:
        operational_signal = 0.0

    raw_confidence = (
        0.25 * source_quality
        + 0.25 * signal_clarity
        + 0.20 * workload_proximity
        + 0.20 * evidence_depth
        + 0.10 * operational_signal
    )

    cap = _confidence_cap(
        matched_evidence_ids=matched_evidence_ids,
        evidence_signals=evidence_signals,
        ai_context=ai_context,
    )
    evidence_conf = min(raw_confidence, cap)

    # Caminho de perfil: quando a rec foi admitida por alinhamento de workload
    # e o perfil esta bem extraido (field_confidence alto), credita isso como
    # fundamentacao real — o perfil aponta para as fontes via field_evidence_ids.
    profile_strength = ai_context.profile_strength if ai_context else 0.0
    profile_conf = (
        0.45 * workload_proximity
        + 0.35 * profile_strength
        + 0.20 * operational_signal
    )
    profile_conf = min(profile_conf, 0.78)  # perfil e prova indireta: teto < 1

    return round(max(evidence_conf, profile_conf), 2)


def _compute_nivel(score: float, confidence: float) -> str:
    """Classifica o nivel da recomendacao numa matriz 2D: relevancia × confianca.

    ``forte``              — score >= 0.60 E confidence >= 0.55
    ``hipotese_prioritaria``— score >= 0.60 mas confidence < 0.55:
                              relevancia alta, mas evidencias insuficientes —
                              a recomendacao merece qualificacao prioritaria,
                              nao pode ser agrupada com hipoteses fracas.
    ``moderada``           — score >= 0.38 E confidence >= 0.25
    ``exploratoria``       — abaixo dos limiares moderados
    """
    if score >= NIVEL_FORTE_SCORE:
        if confidence >= NIVEL_FORTE_CONFIDENCE:
            return NIVEL_FORTE
        return NIVEL_HIPOTESE
    if score >= NIVEL_MODERADA_SCORE and confidence >= NIVEL_MODERADA_CONFIDENCE:
        return NIVEL_MODERADA
    return NIVEL_EXPLORATORIA


def _compute_faltando(
    *,
    nivel: str,
    score_breakdown: dict[str, float],
    confidence: float,
    missing_signals: tuple[str, ...],
    evidence_count: int,
    has_technical_evidence: bool = False,
    has_independent_evidence: bool = False,
    blocked_signals: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Gera lista de sinais ausentes que elevariam ao proximo nivel.

    Para ``forte`` nada falta — lista vazia.
    Para ``moderada`` ou ``exploratoria``, aponta as dimensoes mais fracas.
    Cada item e uma string legivel em portugues, max 5 itens.
    """
    if nivel == NIVEL_FORTE:
        return ()

    items: list[str] = []

    if blocked_signals:
        blocked = ", ".join(blocked_signals[:2])
        items.append(f"contexto negativo bloqueou sinais: {blocked}")

    if nivel == NIVEL_EXPLORATORIA:
        # Para subir a moderada: score >= 0.38 E confidence >= 0.25
        if score_breakdown.get("evidence_signal", 0.0) < 0.35:
            items.append("evidências concretas sobre uso da tecnologia")
        if not has_technical_evidence:
            items.append("fonte tecnica sobre workload, API, docs ou arquitetura")
        if not has_independent_evidence and evidence_count > 0:
            items.append("fonte independente validando a tese")
        if score_breakdown.get("keyword_prior", 0.0) < 0.40 and missing_signals:
            kws = ", ".join(missing_signals[:2])
            items.append(f"sinais ausentes: {kws}")
        if score_breakdown.get("startup_maturity", 0.0) < 0.40:
            items.append("estágio de desenvolvimento declarado")
        if confidence < NIVEL_MODERADA_CONFIDENCE:
            items.append("fontes de evidência com maior confiabilidade")
        if score_breakdown.get("workload_alignment", 0.0) < 0.35:
            items.append("workload alinhado com o perfil da tecnologia")

    elif nivel == NIVEL_MODERADA:
        # Para subir a forte: score >= 0.60 E confidence >= 0.55
        if score_breakdown.get("workload_alignment", 0.0) < 0.60:
            items.append("workload da startup alinhado com a tecnologia")
        if score_breakdown.get("startup_maturity", 0.0) < 0.75:
            items.append("produto em produção ou em escala")
        if not has_technical_evidence:
            items.append("fonte tecnica sobre workload ou implementacao")
        if not has_independent_evidence:
            items.append("fonte independente confirmando o uso")
        if evidence_count < 2:
            items.append("mais evidências independentes sobre a tecnologia")
        elif confidence < NIVEL_FORTE_CONFIDENCE:
            items.append("evidências de maior confiabilidade")
        if missing_signals:
            kws = ", ".join(missing_signals[:2])
            items.append(f"sinais ausentes: {kws}")

    return tuple(items[:5])


def match_technologies(
    *,
    sector: str | None,
    description: str | None,
    ai_maturity_level: str | None = None,
    ai_context: StartupAIContext | None = None,
    evidence_signals: list[EvidenceSignal],
    technologies: list[TechnologyCandidate],
) -> list[MatchResult]:
    """Cruza o perfil da startup com o catalogo NVIDIA usando score composto.

    O filtro de entrada continua exigindo no minimo ``MIN_MATCHED_KEYWORDS``
    keywords (sinal minimo de relevancia) antes de computar o score composto.
    O limiar ``MIN_MATCH_SCORE`` agora e aplicado sobre o score composto (nao
    mais sobre o ratio de keywords), com valor mais baixo (0.20 vs 0.25) para
    compensar que o score composto pondera outros fatores alem de keywords.
    """

    profile_text = " ".join(
        part.lower() for part in (sector, description) if part
    )

    results: list[MatchResult] = []
    for technology in technologies:
        if not technology.keywords:
            continue

        matched_keywords: list[str] = []
        matched_evidence_ids: set[UUID] = set()
        signal_origins: list[str] = []
        missing_signals: list[str] = []
        blocked_signals: list[str] = []

        for keyword in technology.keywords:
            hit_in_profile, blocked_in_profile = _keyword_match_state(
                profile_text, keyword
            )
            evidence_hits: list[UUID] = []
            blocked_in_evidence = False
            for signal in evidence_signals:
                hit, blocked = _keyword_match_state(signal.text, keyword)
                if hit:
                    evidence_hits.append(signal.evidence_id)
                blocked_in_evidence = blocked_in_evidence or blocked

            if hit_in_profile or evidence_hits:
                matched_keywords.append(keyword)
                matched_evidence_ids.update(evidence_hits)
                origin_parts: list[str] = []
                if hit_in_profile:
                    origin_parts.append("setor/descrição")
                for eid in sorted(evidence_hits, key=str):
                    origin_parts.append(f"evidência {str(eid)[:8]}")
                signal_origins.append(f"{keyword}: {', '.join(origin_parts)}")
            else:
                missing_signals.append(keyword)
                if blocked_in_profile or blocked_in_evidence:
                    blocked_signals.append(keyword)
                    signal_origins.append(
                        f"{keyword}: bloqueado por contexto negativo"
                    )

        workload_aln = _workload_alignment(ai_context, technology)
        impl_viab = _implementation_viability(ai_context, technology)
        # Admite por workload quando o perfil estruturado da startup tem
        # alinhamento alto com a tecnologia, mesmo sem keywords literais.
        # Isso deixa workload_alignment votar antes do corte de entrada sem
        # multiplicar fit por confianca: recomendacoes profile-only entram com
        # score/confianca mais baixos e aparecem como hipotese a qualificar.
        admitted_by_workload = (
            ai_context is not None
            and ai_context.ai_workload_type != "unknown"
            and workload_aln >= WORKLOAD_ADMISSION_THRESHOLD
            and _workload_admission_category_allowed(
                ai_context,
                technology,
                matched_keyword_count=len(matched_keywords),
            )
            and not (
                technology.category == "healthcare_ai"
                and len(matched_keywords) == 0
            )
            and len(blocked_signals) == 0
            and impl_viab >= 0.30
        )
        if len(matched_keywords) < MIN_MATCHED_KEYWORDS and not admitted_by_workload:
            continue

        if admitted_by_workload and not matched_keywords:
            signal_origins.append(
                f"workload estruturado: {ai_context.ai_workload_type}"
            )

        keyword_prior = len(matched_keywords) / len(technology.keywords)
        evidence_sig = _evidence_signal_score(
            matched_evidence_ids=matched_evidence_ids,
            evidence_signals=evidence_signals,
            profile_strength=(ai_context.profile_strength if ai_context else 0.0),
        )
        startup_mat = _startup_maturity_score(ai_context)

        score = _composite_score(
            keyword_prior=keyword_prior,
            workload_aln=workload_aln,
            evidence_sig=evidence_sig,
            startup_mat=startup_mat,
            impl_viab=impl_viab,
            ai_maturity_level=ai_maturity_level,
        )

        if score < MIN_MATCH_SCORE:
            continue

        confidence = _composite_confidence(
            evidence_signals=evidence_signals,
            matched_evidence_ids=matched_evidence_ids,
            keyword_prior=keyword_prior,
            workload_aln=workload_aln,
            ai_context=ai_context,
        )

        breakdown = {
            "workload_alignment": round(workload_aln, 2),
            "evidence_signal": round(evidence_sig, 2),
            "startup_maturity": round(startup_mat, 2),
            "keyword_prior": round(keyword_prior, 2),
            "implementation_viability": round(impl_viab, 2),
        }
        nivel = _compute_nivel(score, confidence)
        missing_signals_tuple = tuple(missing_signals)
        if (
            nivel == NIVEL_FORTE
            and not matched_evidence_ids
            and missing_signals_tuple
        ):
            nivel = NIVEL_MODERADA
        matching_evidences = [
            signal
            for signal in evidence_signals
            if signal.evidence_id in matched_evidence_ids
        ]
        faltando = _compute_faltando(
            nivel=nivel,
            score_breakdown=breakdown,
            confidence=round(confidence, 2),
            missing_signals=missing_signals_tuple,
            evidence_count=len(matched_evidence_ids),
            has_technical_evidence=any(
                _is_technical_evidence(signal) for signal in matching_evidences
            ),
            has_independent_evidence=any(
                _is_independent_evidence(signal) for signal in matching_evidences
            ),
            blocked_signals=tuple(blocked_signals),
        )

        results.append(
            MatchResult(
                technology=technology,
                score=round(score, 2),
                confidence=round(confidence, 2),
                matched_keywords=tuple(matched_keywords),
                evidence_ids=tuple(sorted(matched_evidence_ids, key=str)),
                signal_origins=tuple(signal_origins),
                missing_signals=missing_signals_tuple,
                score_breakdown=breakdown,
                nivel=nivel,
                faltando=faltando,
            )
        )

    results.sort(key=lambda result: result.score, reverse=True)
    return results
