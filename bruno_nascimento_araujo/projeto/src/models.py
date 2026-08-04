"""Modelo de dados e helpers de normalizacao."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

STATUS_PENDING = "pending_deep_scan"
STATUS_HIGH = "high_priority"

# Parametros de query de tracking que sujam a URL (UTM, fbclid, etc.).
_TRACKING_PARAM_RE = re.compile(r"[?&](utm_[^=&]+|fbclid|gclid|mc_[^=&]+)=[^&]*", re.IGNORECASE)
_MULTISPACE_RE = re.compile(r"\s+")


def normalize_name(name: str | None) -> str | None:
    """Colapsa espacos e remove ruido de borda. Retorna None se vazio."""
    if not name:
        return None
    cleaned = _MULTISPACE_RE.sub(" ", str(name)).strip()
    return cleaned or None


def normalize_url(url: str | None) -> str | None:
    """Garante scheme, lowercase do host, remove tracking e trailing slash.

    Retorna None se a URL nao tiver host valido.
    """
    if not url:
        return None
    raw = str(url).strip()
    if not raw:
        return None
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw.lstrip("/")
    raw = _TRACKING_PARAM_RE.sub("", raw)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    host = (parsed.netloc or "").lower()
    if not host or "." not in host:
        return None
    path = parsed.path.rstrip("/")
    cleaned = urlunparse((parsed.scheme.lower(), host, path, "", parsed.query, ""))
    return cleaned


def registered_domain(url: str | None) -> str | None:
    """Dominio registravel aproximado (ultimas duas labels) para dedupe/comparacao."""
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    except ValueError:
        return None
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) < 2:
        return host or None
    # Heuristica simples para TLDs compostos br (com.br, org.br, ...).
    if len(labels) >= 3 and labels[-2] in {"com", "org", "net", "gov", "edu"} and labels[-1] == "br":
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


@dataclass
class StartupRecord:
    """Registro normalizado pronto para upsert."""

    name: str
    source_name: str
    sector: str | None = None
    official_website: str | None = None
    source_url: str | None = None
    status: str = STATUS_PENDING

    def __post_init__(self) -> None:
        self.name = normalize_name(self.name) or ""
        self.sector = normalize_name(self.sector)
        self.official_website = normalize_url(self.official_website)
        self.source_url = (self.source_url or None)
        if self.status not in (STATUS_PENDING, STATUS_HIGH):
            self.status = STATUS_PENDING

    def is_valid(self) -> bool:
        return bool(self.name)

    def as_upsert_tuple(self) -> tuple:
        return (
            self.name,
            self.sector,
            self.official_website,
            self.source_name,
            self.source_url,
            self.status,
        )


@dataclass
class Candidate:
    """URL candidata descoberta na fase de busca aberta."""

    url: str
    title: str = ""
    description: str = ""
    source_url: str | None = None
    extras: dict = field(default_factory=dict)

    def text_for_scoring(self) -> str:
        return _MULTISPACE_RE.sub(" ", f"{self.title} {self.description}").strip()
