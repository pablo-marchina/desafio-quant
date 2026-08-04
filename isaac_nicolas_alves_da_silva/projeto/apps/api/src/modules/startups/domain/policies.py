"""Regras deterministicas de dominio do modulo startups."""

import re
from urllib.parse import urlparse

from rapidfuzz import fuzz

from apps.api.src.modules.startups.domain.entities import Startup
from apps.api.src.modules.startups.domain.enums import AiMaturityLevel

NAME_SIMILARITY_THRESHOLD = 92.0
"""Calibrado com pares reais (ver test_startup_deduplication_policy.py).

92 e' o menor valor que ainda captura toda variacao de nome
inequivocamente da mesma empresa observada na calibracao (maiusculas,
espacamento, sufixo legal — "OpenAI"/"Open AI" e' o caso mais baixo,
92.31) sem aceitar nenhum par de empresas diferentes testado (o mais
alto, "Stone"/"StoneAge" e "Acme AI"/"Acme Robotics", fica em 90 —
nome curto + sufixo comum e' uma colisao genuinamente ambigua sem o
dominio como segundo sinal, e o erro mais caro aqui e' fundir duas
empresas diferentes, nao deixar de detectar uma duplicata).
"""

_LEGAL_SUFFIXES = re.compile(
    r"\b(inc|incorporated|ltda|ltd|llc|sa|corp|corporation|co|tecnologia|tech|company)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_AI_SIGNAL_TERMS = (
    "ai",
    "artificial intelligence",
    "agent",
    "agents",
    "assistant",
    "automation",
    "automated",
    "generative",
    "machine learning",
    "llm",
    "large language model",
)

_AI_NATIVE_TERMS = (
    # Model providers / labs / fronteira.
    "frontier ai",
    "foundation model",
    "modelo fundacional",
    "model provider",
    "large language model",
    "modelo de linguagem",
    "llm",
    # Treina / constroi / fine-tunes modelo proprio (EN + PT).
    "train model",
    "trains its own",
    "trains their own",
    "own models",
    "proprietary model",
    "treina modelo",
    "treina os proprios",
    "treina seus proprios",
    "modelo proprio",
    "modelos proprios",
    "modelo proprietario",
    "pre-train",
    "pre-treino",
    "pretraining",
    "fine-tun",
    "fine tun",
    "fine-tuning",
    "ajuste fino",
    "desenvolve modelos de ia",
    "desenvolvemos modelos",
    "cria modelos de ia",
    "nossos modelos",
    "modelos especializados",
    "bertimbau",
    # Arquitetura / pesquisa de modelo.
    "transformer",
    "rede neural",
    "redes neurais",
    "neural network",
    "deep learning",
    "aprendizado profundo",
    "reinforcement learning",
    "aprendizado por reforco",
    "computer vision",
    "visao computacional",
    "model weights",
    "pesos do modelo",
    # Infra de treino/inferencia.
    "training and inference",
    "inference infrastructure",
    "model infrastructure",
    "gpu cluster",
    # Geracao de midia por IA (o modelo e o produto).
    "text-to-video",
    "video generation",
    "generative video",
    "image generation",
    "geracao de imagem",
    "geracao de video",
    "speech synthesis",
    "simulate the world",
)

_AI_ENABLED_PRODUCT_TERMS = (
    "workspace",
    "meeting notes",
    "project management",
    "collaboration",
    "grammar",
    "spelling",
    "presentation",
    "crm",
    "ecommerce",
    "e-commerce",
    "varejo",
    "loja online",
    "design tool",
    "editor de imagem",
    "planilha",
    "spreadsheet",
    "help desk",
    "service desk",
)

_KNOWN_AI_ENABLED_COMPANIES = (
    "notion",
    "grammarly",
    "canva",
    "intercom",
    "zendesk",
    "hubspot",
    "salesforce",
)


def _normalize_name(name: str) -> str:
    normalized = _LEGAL_SUFFIXES.sub("", name.lower())
    return _NON_ALNUM.sub(" ", normalized).strip()


def _compact_name_key(name: str) -> str:
    return _NON_ALNUM.sub("", _normalize_name(name))


def normalize_domain(website_url: str) -> str:
    """Extrai o dominio (sem `www.`/protocolo/path) para comparar URLs."""

    candidate = website_url if "//" in website_url else f"//{website_url}"
    host = urlparse(candidate).netloc.lower()
    return host.removeprefix("www.")


def infer_country_from_url(website_url: str | None) -> str | None:
    """Infere pais apenas quando a URL traz um sinal forte e barato.

    O radar foca startups brasileiras, mas nao deve marcar uma empresa global
    como BR so por ter sido analisada manualmente. Dominios .br sao o unico
    sinal deterministico aplicado aqui.
    """

    if not website_url:
        return None

    domain = normalize_domain(website_url)
    if domain == "br" or domain.endswith(".br"):
        return "BR"
    return None


def find_duplicate_startup(
    *,
    name: str,
    website_url: str | None,
    existing: list[Startup],
) -> Startup | None:
    """Acha, entre `existing`, a startup que provavelmente e' a mesma empresa.

    Dominio (apos normalizar `www.`/protocolo/path) e' o sinal mais
    confiavel: bate exato -> duplicata certa, sem fuzzy. Nome via
    rapidfuzz (`WRatio`) e' so um fallback para quando o dominio nao bate
    ou esta ausente — mais fraco, por isso o limiar e' alto (ver
    `NAME_SIMILARITY_THRESHOLD`).
    """

    candidate_domain = normalize_domain(website_url) if website_url else None
    candidate_name = _normalize_name(name)
    candidate_key = _compact_name_key(name)

    best_match: Startup | None = None
    best_score = 0.0
    for startup in existing:
        if candidate_domain and startup.website_url:
            if normalize_domain(startup.website_url) == candidate_domain:
                return startup

        startup_name_key = _compact_name_key(startup.name)
        startup_url_key = _NON_ALNUM.sub("", (startup.website_url or "").lower())
        # Discovery sometimes first sees a substantive article/profile page and
        # creates "Brand: long article title" with the publisher URL. When the
        # official site is discovered later, exact-domain matching cannot help.
        # For brand names long enough to be distinctive, treat containment in
        # the existing title or source URL as a strong duplicate signal.
        if len(candidate_key) >= 8 and (
            candidate_key in startup_name_key or candidate_key in startup_url_key
        ):
            return startup

        score = fuzz.WRatio(candidate_name, _normalize_name(startup.name))
        if score > best_score:
            best_score = score
            best_match = startup

    if best_match is not None and best_score >= NAME_SIMILARITY_THRESHOLD:
        return best_match
    return None


def calibrate_ai_maturity_level(
    *,
    level: AiMaturityLevel,
    reason: str,
    name: str,
    sector: str | None,
    description: str | None,
    website_url: str | None,
    evidence_texts: list[str],
) -> tuple[AiMaturityLevel, str]:
    """Aplica a regua do TAP apos a classificacao semantica.

    O TAP diferencia empresas cujo produto central e IA (AI-native) de
    produtos maiores que incorporam IA como camada relevante (AI-enabled).
    LLMs tendem a superclassificar produtos com muito marketing de "AI" como
    AI-native; esta politica estabiliza casos canonicos como Notion AI,
    Grammarly e Canva AI.
    """

    text = " ".join(
        part.lower()
        for part in [
            name,
            sector or "",
            description or "",
            website_url or "",
            reason,
            *evidence_texts,
        ]
        if part
    )

    has_ai_signal = any(term in text for term in _AI_SIGNAL_TERMS)
    has_native_signal = any(term in text for term in _AI_NATIVE_TERMS)
    has_enabled_product_signal = any(
        term in text for term in _AI_ENABLED_PRODUCT_TERMS
    )
    is_known_enabled_company = any(
        company in text for company in _KNOWN_AI_ENABLED_COMPANIES
    )

    if (
        level is AiMaturityLevel.AI_NATIVE
        and has_ai_signal
        and (has_enabled_product_signal or is_known_enabled_company)
        and not has_native_signal
    ):
        return (
            AiMaturityLevel.AI_ENABLED,
            (
                "Classificacao ajustada pela regua do TAP: ha sinais fortes "
                "de IA, mas como camada de produto/workflow dentro de uma "
                f"oferta mais ampla, nao como empresa cujo core e vender IA. {reason}"
            ),
        )

    if (
        level is AiMaturityLevel.NON_AI
        and has_ai_signal
        and (has_enabled_product_signal or is_known_enabled_company)
    ):
        return (
            AiMaturityLevel.AI_ENABLED,
            (
                "Classificacao ajustada pela regua do TAP: a evidencia aponta "
                "uso relevante de IA dentro de um produto mais amplo. "
                f"{reason}"
            ),
        )

    return level, reason
