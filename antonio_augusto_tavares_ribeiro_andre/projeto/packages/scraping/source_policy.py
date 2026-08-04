"""Política de ToS por fonte: robots ≠ ToS (F1.15).

O DoD do F1 promete "nenhuma fonte fechada/violação de ToS", mas o `robots.txt`
(F1.8) **não** é o ToS: uma plataforma de dados (§9.1 — Distrito, Cubo, StartSe, 100
Open Startups, Crunchbase…) pode **proibir scraping no ToS** mesmo com robots permissivo.
Decisão travada: **priorizar sites/blogs/carreiras oficiais das startups + notícias
(§9.2)**; usar os diretórios §9.1 **só** onde houver API/permissão. Fonte sem permissão
clara → não coletada.

Este módulo é o **gate de ToS por URL** para o caminho do roteador (F1.7), espelhando o
que `collectable_seeds` (F1.6) já faz para a varredura do crawler:

- mapeia a URL → a **fonte governante** (por host) das seeds (`data/seeds/`, F0.9);
- `verdict(url)` decide: fonte `allow` ou **não-listada** (site oficial/notícia) → coleta
  liberada; fonte `api_only`/`deny` (§9.1 proprietária) → **bloqueada** (usar API/parceria);
- `guard(url)` levanta `ToSProhibited` (subclasse de `ComplianceError`, F1.8) p/ o caller
  abortar **antes** do fetch; `annotation` é a base por-fonte que a persistência carimba em
  `evidence.source_policy` (auditável: cada evidência diz sob qual política foi coletada).

A allowlist/denylist canônica vive nas seeds (cada fonte com `policy`/`robots`/
`tos_scraping`/`legal_basis`); aqui é a **aplicação** dela. Tudo puro/offline (lê os YAMLs
locais via F0.9, sem rede). Default seguro p/ host não-listado: **liberar** — são os sites
oficiais/imprensa que a decisão prioriza; o que se barra são as plataformas proprietárias
**conhecidas**. O robots/rate-limit continua sendo aplicado por cima (F1.8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlsplit

from .compliance import ComplianceError
from .seeds import Source, load_sources

# Hosts placeholder das seeds (ex.: a entrada "canais oficiais") — não governam URL real.
_PLACEHOLDER_HOSTS = frozenset({"example.com", "example.org", "example.net"})


class ToSProhibited(ComplianceError):
    """Levantada quando o ToS da fonte proíbe coletar a URL diretamente (F1.15)."""

    def __init__(self, url: str, source_id: str, policy: str) -> None:
        super().__init__(
            f"ToS da fonte {source_id!r} ({policy}) proíbe coletar {url!r} direto — "
            f"usar API/parceria (F1.15)"
        )
        self.url = url
        self.source_id = source_id
        self.policy = policy


def _host(url: str) -> str:
    """Host normalizado (minúsculo, sem `www.`) de uma URL; vazio se não der p/ parsear."""
    raw = url if "://" in url else "//" + url
    host = (urlsplit(raw).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


@dataclass(frozen=True)
class SourceVerdict:
    """Decisão de ToS para uma URL: pode coletar? por quê? sob qual base?"""

    allowed: bool
    reason: str
    source_id: str | None = None
    policy: str | None = None  # allow | api_only | deny | unlisted
    robots: str | None = None
    tos_scraping: str | None = None
    legal_basis: str | None = None

    @property
    def annotation(self) -> str:
        """Anotação compacta p/ `evidence.source_policy`: '<fonte>:<policy>'.

        Fonte não-listada (site oficial/notícia) → 'unlisted:allow' (liberada por padrão).
        """
        if self.source_id is None:
            return "unlisted:allow"
        return f"{self.source_id}:{self.policy}"


@dataclass
class SourcePolicyGate:
    """Aplica a política de ToS por fonte (F1.15) sobre URLs avulsas (caminho do roteador).

    Carrega a allowlist/denylist das seeds (F0.9) e casa a URL ao host mais específico de
    uma fonte conhecida. `default_gate()` dá a instância cacheada do módulo.
    """

    sources: tuple[Source, ...] = field(default_factory=load_sources)

    def _match(self, url: str) -> Source | None:
        """Fonte governante da URL = a de host mais específico que casa (ou subdomínio)."""
        host = _host(url)
        if not host or host in _PLACEHOLDER_HOSTS:
            return None
        best: Source | None = None
        best_len = -1
        for src in self.sources:
            sh = _host(src.url)
            if not sh or sh in _PLACEHOLDER_HOSTS:
                continue
            if (host == sh or host.endswith("." + sh)) and len(sh) > best_len:
                best, best_len = src, len(sh)
        return best

    def verdict(self, url: str) -> SourceVerdict:
        """Decide a coleta de `url` pela política de ToS da fonte governante (F1.15)."""
        src = self._match(url)
        if src is None:
            return SourceVerdict(
                allowed=True,
                reason="fonte não-listada (site oficial/notícia) — liberada por padrão (F1.15)",
                policy="unlisted",
                legal_basis="conteúdo público da própria empresa/imprensa",
            )
        common = {
            "source_id": src.id,
            "policy": src.policy,
            "robots": src.robots,
            "tos_scraping": src.tos_scraping,
            "legal_basis": src.legal_basis,
        }
        if src.collectable:  # policy == "allow"
            return SourceVerdict(allowed=True, reason=f"fonte '{src.id}' allow", **common)
        return SourceVerdict(
            allowed=False,
            reason=f"fonte '{src.id}' {src.policy}: ToS proíbe scraping direto (usar API/parceria)",
            **common,
        )

    def allowed(self, url: str) -> bool:
        """True se a URL pode ser coletada sob a política de ToS (F1.15)."""
        return self.verdict(url).allowed

    def guard(self, url: str) -> None:
        """Levanta `ToSProhibited` se a URL não pode ser coletada (chamar antes do fetch)."""
        v = self.verdict(url)
        if not v.allowed:
            raise ToSProhibited(url, v.source_id or "?", v.policy or "?")

    def annotate(self, url: str) -> str:
        """Anotação por-fonte p/ carimbar em `evidence.source_policy` (auditoria)."""
        return self.verdict(url).annotation


@lru_cache
def default_gate() -> SourcePolicyGate:
    """Gate cacheado do módulo (seeds carregadas uma vez)."""
    return SourcePolicyGate()


def verdict(url: str) -> SourceVerdict:
    """`verdict` via gate default (F1.15)."""
    return default_gate().verdict(url)


def allowed(url: str) -> bool:
    """`allowed` via gate default (F1.15)."""
    return default_gate().allowed(url)


def guard(url: str) -> None:
    """`guard` via gate default — levanta `ToSProhibited` se barrado (F1.15)."""
    default_gate().guard(url)


def annotate(url: str) -> str:
    """Anotação por-fonte (`evidence.source_policy`) via gate default (F1.15)."""
    return default_gate().annotate(url)


__all__ = [
    "ToSProhibited",
    "SourceVerdict",
    "SourcePolicyGate",
    "default_gate",
    "verdict",
    "allowed",
    "guard",
    "annotate",
]
