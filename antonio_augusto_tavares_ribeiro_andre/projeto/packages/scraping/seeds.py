"""Carregamento das seed lists de fontes do §9 (F0.9).

Lê os YAMLs de `data/seeds/` (diretórios §9.1, notícias §9.2, programas de descoberta)
num modelo tipado `Source`, com a **decisão de coleta** por fonte (allowlist/denylist,
F1.15). Consumido pelo `search_planner` (F2.3), pelo crawler Scrapy (F1.6) e pela guarda
de ToS (F1.15). A checagem vinculante de robots/rate-limit roda em runtime (F1.8) — aqui
fica a **intenção declarada**.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

SourceType = Literal["directory", "news", "program"]
Policy = Literal["allow", "api_only", "deny"]

# data/seeds/ na raiz do repo (packages/scraping/seeds.py -> parents[2] == raiz).
SEEDS_DIR = Path(__file__).resolve().parents[2] / "data" / "seeds"

_TYPES = ("directory", "news", "program")
_POLICIES = ("allow", "api_only", "deny")


@dataclass(frozen=True)
class Source:
    """Uma fonte de sourcing (§9) com sua decisão de coleta."""

    id: str
    name: str
    url: str
    type: SourceType
    country: str
    policy: Policy
    robots: str
    tos_scraping: str
    legal_basis: str
    notes: str = ""

    @property
    def collectable(self) -> bool:
        """True só quando a coleta direta está liberada (allowlist)."""
        return self.policy == "allow"


def _coerce(raw: dict, *, file: str) -> Source:
    missing = {"id", "name", "url", "type", "country", "policy"} - raw.keys()
    if missing:
        raise ValueError(f"{file}: fonte sem campos {sorted(missing)}: {raw.get('id', raw)!r}")
    if raw["type"] not in _TYPES:
        raise ValueError(f"{file}: type inválido {raw['type']!r} em {raw['id']!r}")
    if raw["policy"] not in _POLICIES:
        raise ValueError(f"{file}: policy inválida {raw['policy']!r} em {raw['id']!r}")
    if not str(raw["url"]).startswith("http"):
        raise ValueError(f"{file}: url não-http em {raw['id']!r}: {raw['url']!r}")
    # Consistência da política (F1.15): só se coleta o que os ToS não proíbem.
    if raw["policy"] == "allow" and raw.get("tos_scraping") == "prohibited":
        raise ValueError(f"{file}: {raw['id']!r} é allow mas ToS=prohibited — contraditório")
    return Source(
        id=raw["id"],
        name=raw["name"],
        url=raw["url"],
        type=raw["type"],
        country=raw["country"],
        policy=raw["policy"],
        robots=raw.get("robots", "unknown"),
        tos_scraping=raw.get("tos_scraping", "unknown"),
        legal_basis=raw.get("legal_basis", ""),
        notes=raw.get("notes", ""),
    )


@lru_cache
def load_sources() -> tuple[Source, ...]:
    """Todas as fontes dos YAMLs de `data/seeds/` (cacheado). IDs são únicos."""
    sources: list[Source] = []
    seen: set[str] = set()
    for path in sorted(SEEDS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in data.get("sources", []):
            src = _coerce(raw, file=path.name)
            if src.id in seen:
                raise ValueError(f"id de fonte duplicado: {src.id!r}")
            seen.add(src.id)
            sources.append(src)
    if not sources:
        raise ValueError(f"nenhuma fonte carregada de {SEEDS_DIR}")
    return tuple(sources)


def allowlist() -> tuple[Source, ...]:
    """Fontes com coleta direta liberada (`policy: allow`)."""
    return tuple(s for s in load_sources() if s.policy == "allow")


def denylist() -> tuple[Source, ...]:
    """Fontes que não podem ser coletadas direto (`api_only` ou `deny`)."""
    return tuple(s for s in load_sources() if s.policy != "allow")


def by_type(source_type: SourceType) -> tuple[Source, ...]:
    """Fontes de um tipo (`directory` §9.1 · `news` §9.2 · `program` descoberta)."""
    return tuple(s for s in load_sources() if s.type == source_type)
