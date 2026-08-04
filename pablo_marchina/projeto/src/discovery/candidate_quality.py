from __future__ import annotations

"""Quality gates for turning scraped links into startup candidates.

The discovery layer must not promote navigation links, social profiles, generic
words, or media accounts as companies.  These gates are intentionally
quantitative and auditable: each rejection returns a machine-readable reason and
feature values so the decision can be inspected in the dashboard/runtime logs.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

_GENERIC_NAMES = {
    "ai",
    "ia",
    "startup",
    "startups",
    "empresa",
    "empresas",
    "portfolio",
    "portfólio",
    "case",
    "cases",
    "blog",
    "newsletter",
    "youtube",
    "instagram",
    "linkedin",
    "facebook",
    "twitter",
    "x",
    "tiktok",
    "whatsapp",
    "telegram",
    "contato",
    "contact",
    "home",
    "início",
    "inicio",
    "menu",
    "login",
    "entrar",
    "cadastro",
    "saiba mais",
    "learn more",
    "read more",
    "ver mais",
    "conheça",
    "acesse",
    "eventos",
    "programas",
    "sobre",
    "about",
    "founders",
    "fundadores",
    "investidores",
    "vagas",
    "carreiras",
    "jobs",
    "programa",
    "programas",
    "aceleração",
    "aceleracao",
    "divulgação",
    "divulgacao",
    "mantenedores",
    "parcerias",
    "parceiros",
    "patrocinadores",
    "cart",
    "carrinho",
    "loja",
    "store",
    "startuprun",
    "startup run",
    "ranking",
    "ecossistema",
    "ecosystem",
    "associação",
    "associacao",
    "associados",
    "membros",
    "members",
}

_BLOCKED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    "tiktok.com",
    "www.tiktok.com",
    "wa.me",
    "api.whatsapp.com",
    "whatsapp.com",
    "t.me",
    "telegram.me",
    "open.spotify.com",
    "spotify.com",
    "linktr.ee",
    "bit.ly",
    "tinyurl.com",
    "example.com",
    "www.example.com",
}

_BLOCKED_PATH_TERMS = (
    "/login",
    "/signin",
    "/sign-in",
    "/signup",
    "/register",
    "/contato",
    "/contact",
    "/privacy",
    "/terms",
    "/politica",
    "/blog",
    "/news",
    "/noticias",
    "/eventos",
    "/events",
    "/podcast",
    "/youtube",
    "/instagram",
    "/facebook",
    "/linkedin",
)

_ALLOWED_COMPANY_SOCIAL_DOMAINS = {
    "linkedin.com",
    "www.linkedin.com",
    "br.linkedin.com",
}

_CORPORATE_SUFFIX_PATTERN = re.compile(r"\b(sa|s\.a\.|ltda|me|eireli|inc|corp|labs?|tech|ai|ia)\b", re.I)
_GENERIC_PHRASE_PATTERNS = (
    r"\bprogramas?\s+de\s+acelera",
    r"\bdivulga[çc][aã]o\s+de\s+eventos",
    r"\bmantenedores?\b",
    r"\bparcerias?\b",
    r"\bpatrocinadores?\b",
    r"\bstartup\s*run\b",
    r"\b(carrinho|cart|checkout)\b",
    r"\b(youtube|instagram|facebook|linkedin|tiktok)\b",
)
_DIRECTORY_OR_AGGREGATOR_DOMAINS = {
    "startupbase.com.br",
    "www.startupbase.com.br",
    "darwinstartups.com",
    "www.darwinstartups.com",
    "abstartups.com.br",
    "www.abstartups.com.br",
    "100openstartups.com",
    "www.100openstartups.com",
    "cubo.network",
    "www.cubo.network",
    "latitud.com",
    "www.latitud.com",
    "bossainvest.com",
    "www.bossainvest.com",
    "acestartups.com.br",
    "www.acestartups.com.br",
    "distrito.me",
    "www.distrito.me",
}
_GLOBAL_NON_STARTUP_NAMES = {
    "xiaomi",
    "google",
    "microsoft",
    "amazon",
    "meta",
    "nvidia",
    "openai",
    "anthropic",
    "apple",
}



@dataclass(frozen=True)
class CandidateQualityResult:
    accepted: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    features: dict[str, float | str | bool] = field(default_factory=dict)


def normalize_candidate_name(name: str) -> str:
    clean = re.sub(r"\s+", " ", str(name or "").strip())
    clean = clean.strip(" -|•·:;,.\t\n\r")
    clean = re.sub(r"^(conheça|saiba mais sobre|saiba mais|acesse|ver|veja)\s+", "", clean, flags=re.I)
    clean = re.sub(r"\s+(no youtube|no instagram|no linkedin|on youtube|on instagram)$", "", clean, flags=re.I)
    return clean.strip()


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.casefold()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _path(url: str) -> str:
    try:
        return urlparse(url).path.casefold()
    except Exception:
        return ""


def is_blocked_website(url: str) -> bool:
    if not url:
        return False
    domain = _domain(url)
    if domain in _BLOCKED_DOMAINS:
        return True
    path = _path(url)
    if any(term in path for term in _BLOCKED_PATH_TERMS):
        # LinkedIn company pages are useful evidence, but they should not be treated as official websites.
        return domain not in _ALLOWED_COMPANY_SOCIAL_DOMAINS
    return False


def is_directory_or_aggregator_url(url: str) -> bool:
    return _domain(url) in _DIRECTORY_OR_AGGREGATOR_DOMAINS


def _looks_like_company_name(name: str) -> bool:
    if not name:
        return False
    lower = name.casefold()
    if lower in _GENERIC_NAMES or lower in _GLOBAL_NON_STARTUP_NAMES:
        return False
    if any(re.search(pattern, lower, re.I) for pattern in _GENERIC_PHRASE_PATTERNS):
        return False
    tokens = [t for t in re.split(r"\s+", lower) if t]
    if tokens and all(t in _GENERIC_NAMES for t in tokens):
        return False
    if any(t in _GLOBAL_NON_STARTUP_NAMES for t in tokens) and len(tokens) <= 2:
        return False
    if len(name) < 2 or len(name) > 80:
        return False
    if len(tokens) > 7 and not _CORPORATE_SUFFIX_PATTERN.search(name):
        return False
    if not re.search(r"[A-Za-zÀ-ÿ0-9]", name):
        return False
    if re.search(r"\b(copyright|todos os direitos|política de privacidade|termos de uso)\b", lower):
        return False
    return True


def evaluate_candidate_quality(
    *,
    name: str,
    website: str = "",
    description: str = "",
    source_id: str = "",
    signal_count: int = 0,
    evidence_count: int = 0,
) -> CandidateQualityResult:
    clean_name = normalize_candidate_name(name)
    reasons: list[str] = []
    score = 0.0

    has_name = _looks_like_company_name(clean_name)
    has_website = bool(str(website or "").strip())
    blocked_website = is_blocked_website(website)
    has_description = bool(str(description or "").strip())

    if has_name:
        score += 0.35
    else:
        reasons.append("invalid_or_generic_company_name")
    directory_or_aggregator_website = is_directory_or_aggregator_url(website)
    if has_website and not blocked_website and not directory_or_aggregator_website:
        score += 0.25
    elif blocked_website:
        reasons.append("blocked_social_or_navigation_website")
    elif directory_or_aggregator_website:
        reasons.append("directory_or_aggregator_url_is_not_company_website")
    if signal_count > 0:
        score += min(0.25, 0.08 * signal_count)
    else:
        reasons.append("no_ai_native_signal_in_candidate_text")
    if evidence_count > 0:
        score += min(0.10, 0.02 * evidence_count)
    if has_description:
        score += 0.05

    # A company can only enter the runtime pipeline when the AI signal comes from
    # the entity text itself. Source-level labels such as “AI directory” are not
    # evidence that a specific listed item is AI-native.
    accepted = has_name and not blocked_website and not directory_or_aggregator_website and signal_count > 0 and score >= 0.45
    if not accepted and not reasons:
        reasons.append("candidate_quality_score_below_threshold")

    return CandidateQualityResult(
        accepted=accepted,
        score=round(max(0.0, min(1.0, score)), 4),
        reasons=reasons,
        features={
            "clean_name": clean_name,
            "has_name": has_name,
            "has_website": has_website,
            "blocked_website": blocked_website,
            "directory_or_aggregator_website": directory_or_aggregator_website,
            "has_description": has_description,
            "signal_count": signal_count,
            "evidence_count": evidence_count,
            "source_id": source_id,
        },
    )
