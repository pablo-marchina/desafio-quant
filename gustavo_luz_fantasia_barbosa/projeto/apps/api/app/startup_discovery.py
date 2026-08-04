from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from app.scraping import crawl_public_website_text, response_text
from app.startup_sources import (
    load_startup_candidates,
    normalize_text,
    resolve_source_path,
    write_startup_candidates,
)


DISCOVERY_FIELDS = [
    "startup_name",
    "country_code",
    "sector",
    "stage",
    "source",
    "website_url",
    "github_url",
    "source_url",
    "article_title",
    "article_url",
    "description",
    "signals",
    "confidence",
    "discovered_at",
    "status",
]

DEFAULT_DISCOVERY_SOURCE_URLS = (
    "https://startupi.com.br/",
    "https://startupi.com.br/startups/",
    "https://revistapegn.globo.com/startups/",
)

DISCOVERY_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NVIDIA-Startup-AI-Radar/0.1; "
        "+https://localhost)"
    )
}

STARTUP_ACTION_PATTERNS = (
    " levanta ",
    " capta ",
    " recebe ",
    " anuncia ",
    " lança ",
    " expande ",
    " cresce ",
    " fecha ",
    " compra ",
    " adquire ",
    " investe ",
    " acelera ",
    " estreia ",
    " chega ",
)

BLOCKED_NAMES = {
    "a",
    "accenture",
    "as",
    "batalha",
    "banco",
    "brasil",
    "com",
    "dell",
    "ebitda",
    "google",
    "meeting",
    "microsoft",
    "nvidia",
    "oracle",
    "para",
    "por",
    "startup",
    "startups",
    "startupi",
}

STARTUP_ENTITY_PREFIXES = (
    "startup",
    "fintech",
    "healthtech",
    "edtech",
    "logtech",
    "deeptech",
    "insurtech",
    "agtech",
    "retailtech",
    "lawtech",
    "empresa",
)

SECTOR_RULES = [
    ("fintech", ("fintech", "financeira", "pagamento", "credito", "banco", "pix", "investimento", "anjo")),
    ("healthcare", ("healthtech", "saude", "medicina", "clinica", "hospital")),
    ("logistics", ("logistica", "frete", "rota", "entrega", "importador")),
    ("cybersecurity", ("seguranca", "fraude", "identidade", "kyc", "risco")),
    ("education", ("edtech", "educacao", "educacional", "ensino", "professor", "aluno")),
    ("data", ("dados", "analytics", "inteligencia artificial", "ia", "machine learning")),
    ("developer_tools", ("dev", "software", "plataforma", "automacao", "api")),
]

BLOCKED_EXTERNAL_DOMAINS = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "threads.net",
    "youtube.com",
    "youtu.be",
    "whatsapp.com",
    "wa.me",
    "telegram.org",
    "t.me",
    "pinterest.com",
    "google.com",
    "gazetamercantil.digital",
    "startupi.com.br",
)


class LinkTextParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self._active_href: str | None = None
        self._parts: list[str] = []
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        href = dict(attrs).get("href")
        if not href:
            return

        self._active_href = urljoin(self.base_url, href)
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._active_href:
            text = " ".join(data.split())
            if text:
                self._parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._active_href:
            return

        title = " ".join(self._parts).strip()
        if title:
            self.links.append({"title": title, "url": self._active_href})
        self._active_href = None
        self._parts = []


def clean_candidate_name(value: str) -> str:
    name = re.sub(r"^[\"'“”‘’]+|[\"'“”‘’]+$", "", value.strip())
    name = re.sub(r"^(a|o|as|os|uma|um)\s+", "", name, flags=re.I)
    name = re.sub(
        r"^(m&a|ma|rodada|aporte|startup|startups|fintech|healthtech|edtech|logtech|deeptech|agtech|retailtech|lawtech|negocios|inovacao)\s+",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(r"\s+", " ", name)
    return name.strip(" :;-")


def extract_startup_name(title: str) -> str | None:
    normalized_title = f" {normalize_text(title)} "
    lower_title = title.lower()

    for pattern in STARTUP_ACTION_PATTERNS:
        if pattern in normalized_title:
            index = normalize_text(title).find(pattern.strip())
            if index <= 0:
                continue
            prefix_candidate = title[:index]
            direct_name = validate_candidate_name(prefix_candidate)
            if direct_name:
                return direct_name

            capitalized_name = re.search(
                r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.&-]*(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.&-]*){0,2})$",
                prefix_candidate.strip(" ,:-"),
            )
            if capitalized_name:
                extracted = validate_candidate_name(capitalized_name.group(1))
                if extracted:
                    return extracted

    prefix_pattern = "|".join(STARTUP_ENTITY_PREFIXES)
    typed_match = re.search(
        rf"(?i:\b(?:{prefix_pattern})\b)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.&-]*(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.&-]*){{0,2}})",
        title,
    )
    if typed_match:
        extracted = validate_candidate_name(typed_match.group(1))
        if extracted:
            return extracted

    startup_match = re.search(
        r"\bstartups?\b\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.&-]*(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.&-]*){0,3})",
        title,
    )
    if startup_match:
        return validate_candidate_name(startup_match.group(1))

    return None


def validate_candidate_name(value: str) -> str | None:
    name = clean_candidate_name(value)
    normalized = normalize_text(name)
    words = [word for word in normalized.split() if word]

    if not name or len(name) < 2 or len(words) > 4:
        return None
    if words[0] in BLOCKED_NAMES or normalized in BLOCKED_NAMES:
        return None
    if "startup" in words or "startups" in words:
        return None
    if any(character.isdigit() for character in name):
        return None

    return name


def startup_name_key(value: object) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    words = [
        word
        for word in normalized.split()
        if word not in {"ltda", "sa", "s", "a", "me", "eireli"}
    ]
    return " ".join(words).strip()


def source_label_from_url(source_url: str) -> str:
    host = urlparse(source_url).netloc.lower().removeprefix("www.")
    if host.endswith("startupi.com.br"):
        return "startupi"
    if host.endswith("startups.com.br"):
        return "startups_com_br"
    if host.endswith("exame.com"):
        return "exame"
    if host.endswith("braziljournal.com"):
        return "brazil_journal"
    if host.endswith("startse.com"):
        return "startse"
    if host.endswith("endeavor.org.br"):
        return "endeavor"
    if host.endswith("aceventures.com.br") or host.endswith("acestartups.com.br"):
        return "ace"
    if host.endswith("distrito.me"):
        return "distrito"
    if host.endswith("revistapegn.globo.com"):
        return "pegnglobo"
    if host.endswith("valor.globo.com"):
        return "valor"
    label = re.sub(r"[^a-z0-9]+", "_", host).strip("_")
    return label or "news"


@dataclass
class DiscoverySourceAdapter:
    source_url: str
    source_label: str | None = None

    @property
    def label(self) -> str:
        return self.source_label or source_label_from_url(self.source_url)

    def fetch_links(self) -> tuple[str, list[dict[str, str]]]:
        response = requests.get(
            self.source_url,
            timeout=20,
            headers=DISCOVERY_REQUEST_HEADERS,
        )
        response.raise_for_status()
        return response.url, self.parse_links(response_text(response), response.url)

    def parse_links(self, html: str, response_url: str | None = None) -> list[dict[str, str]]:
        parser = LinkTextParser(response_url or self.source_url)
        parser.feed(html)
        return parser.links

    def accepts_link(self, article_url: str, response_url: str) -> bool:
        return urlparse(article_url).netloc == urlparse(response_url).netloc

    def normalize_title(self, title: str) -> str:
        return " ".join(title.split())

    def build_discovery(
        self,
        *,
        startup_name: str,
        title: str,
        article_url: str,
        discovered_at: str,
    ) -> dict[str, object]:
        sector, signals = infer_sector_and_signals(title, self.label)
        return {
            "startup_name": startup_name,
            "country_code": "BR",
            "sector": sector,
            "stage": "",
            "source": f"{self.label}_news",
            "website_url": "",
            "github_url": "",
            "source_url": article_url,
            "article_title": title,
            "article_url": article_url,
            "description": title,
            "signals": signals,
            "confidence": 68 if sector != "unknown" else 54,
            "discovered_at": discovered_at,
            "status": "new",
        }

    def collect_from_links(
        self,
        links: list[dict[str, str]],
        *,
        response_url: str | None = None,
        max_items: int = 20,
    ) -> list[dict[str, object]]:
        discovered_at = datetime.now(timezone.utc).isoformat()
        discoveries = []
        seen: set[str] = set()
        resolved_response_url = response_url or self.source_url

        for link in links:
            article_url = link["url"].split("#", 1)[0]
            if not self.accepts_link(article_url, resolved_response_url):
                continue

            title = self.normalize_title(link["title"])
            if len(title) < 12 or len(title) > 180:
                continue

            startup_name = extract_startup_name(title)
            if not startup_name:
                continue

            item = self.build_discovery(
                startup_name=startup_name,
                title=title,
                article_url=article_url,
                discovered_at=discovered_at,
            )
            key = discovery_key(item)
            if key in seen:
                continue
            seen.add(key)
            discoveries.append(item)
            if len(discoveries) >= max_items:
                break

        return discoveries

    def collect(self, max_items: int = 20) -> list[dict[str, object]]:
        response_url, links = self.fetch_links()
        return self.collect_from_links(
            links,
            response_url=response_url,
            max_items=max_items,
        )


class StartupiDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "startupi"


class StartupsComBrDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "startups_com_br"


class ExameDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "exame"


class BrazilJournalDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "brazil_journal"


class StartSeDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "startse"


class EndeavorDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "endeavor"


class ACEDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "ace"


class DistritoDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "distrito"


class PEGNDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "pegn"


class ValorDiscoveryAdapter(DiscoverySourceAdapter):
    @property
    def label(self) -> str:
        return self.source_label or "valor"


class GenericNewsDiscoveryAdapter(DiscoverySourceAdapter):
    pass


DISCOVERY_ADAPTERS: tuple[tuple[str, type[DiscoverySourceAdapter]], ...] = (
    ("startupi.com.br", StartupiDiscoveryAdapter),
    ("startups.com.br", StartupsComBrDiscoveryAdapter),
    ("exame.com", ExameDiscoveryAdapter),
    ("braziljournal.com", BrazilJournalDiscoveryAdapter),
    ("startse.com", StartSeDiscoveryAdapter),
    ("endeavor.org.br", EndeavorDiscoveryAdapter),
    ("aceventures.com.br", ACEDiscoveryAdapter),
    ("acestartups.com.br", ACEDiscoveryAdapter),
    ("distrito.me", DistritoDiscoveryAdapter),
    ("revistapegn.globo.com", PEGNDiscoveryAdapter),
    ("valor.globo.com", ValorDiscoveryAdapter),
)


def discovery_adapter_for_url(
    source_url: str,
    source_label: str | None = None,
) -> DiscoverySourceAdapter:
    host = urlparse(source_url).netloc.lower().removeprefix("www.")
    for domain, adapter_type in DISCOVERY_ADAPTERS:
        if host == domain or host.endswith(f".{domain}"):
            return adapter_type(source_url=source_url, source_label=source_label)
    return GenericNewsDiscoveryAdapter(source_url=source_url, source_label=source_label)


def parse_discovery_source_urls(value: str | None, fallback: str | None = None) -> list[str]:
    candidates = [
        item.strip()
        for item in str(value or "").split(",")
        if item.strip()
    ]
    if not candidates and fallback:
        candidates = [fallback.strip()]
    if not candidates:
        candidates = list(DEFAULT_DISCOVERY_SOURCE_URLS)

    urls = []
    for candidate in candidates:
        if not candidate.startswith(("http://", "https://")):
            continue
        if candidate not in urls:
            urls.append(candidate)
    return urls


def infer_sector_and_signals(title: str, source_label: str = "startupi") -> tuple[str, list[str]]:
    normalized = normalize_text(title)
    signals = ["noticia", source_label, "Brasil"]
    for sector, terms in SECTOR_RULES:
        matched = [term for term in terms if term in normalized]
        if matched:
            return sector, signals + matched[:3]
    return "unknown", signals


def compact(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_text(value))


def is_blocked_external_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not parsed.scheme.startswith("http") or not host:
        return True
    if any(host == domain or host.endswith(f".{domain}") for domain in BLOCKED_EXTERNAL_DOMAINS):
        return True

    share_surface = f"{parsed.path}?{parsed.query}".lower()
    return any(
        marker in share_surface
        for marker in (
            "/share",
            "/send",
            "sharer",
            "intent/tweet",
            "share?",
            "share=",
            "text=http",
        )
    )


def official_link_score(startup_name: str, url: str, title: str = "") -> int:
    if not url.startswith(("http://", "https://")) or is_blocked_external_url(url):
        return 0

    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    name_key = compact(startup_name)
    host_key = compact(host.split(".")[0])
    url_key = compact(url)
    title_key = compact(title)

    score = 0
    if name_key and name_key == host_key:
        score += 100
    elif name_key and (name_key in host_key or host_key in name_key):
        score += 70
    elif name_key and name_key in url_key:
        score += 45
    elif name_key and name_key in title_key:
        score += 35

    if host.endswith(".br") or ".com.br" in host:
        score += 8
    if any(term in url.lower() for term in ("utm_", "share", "author", "tag")):
        score -= 10
    return max(0, score)


def choose_official_website(
    startup_name: str,
    article_url: str,
    links: list[dict[str, str]],
) -> str | None:
    article_host = urlparse(article_url).netloc.lower()
    ranked = []
    for link in links:
        url = link.get("url", "").split("#", 1)[0]
        if not url:
            continue
        if urlparse(url).netloc.lower() == article_host:
            continue
        score = official_link_score(startup_name, url, link.get("title", ""))
        if score >= 45:
            ranked.append((score, url))

    ranked.sort(reverse=True)
    return ranked[0][1] if ranked else None


def fetch_article_links(article_url: str) -> list[dict[str, str]]:
    response = requests.get(
        article_url,
        timeout=20,
        headers=DISCOVERY_REQUEST_HEADERS,
    )
    response.raise_for_status()

    parser = LinkTextParser(response.url)
    parser.feed(response_text(response))
    return parser.links


def enrich_discovery_with_public_evidence(discovery: dict[str, object]) -> dict[str, object]:
    startup_name = str(discovery.get("startup_name") or "").strip()
    article_url = str(discovery.get("article_url") or discovery.get("source_url") or "").strip()
    if not startup_name or not article_url:
        return {**discovery, "status": "enrichment_skipped"}

    website_url = str(discovery.get("website_url") or "").strip()
    enriched = dict(discovery)
    if website_url and is_blocked_external_url(website_url):
        website_url = ""

    if not website_url:
        links = fetch_article_links(article_url)
        website_url = choose_official_website(startup_name, article_url, links) or ""

    if not website_url:
        enriched["signals"] = [
            signal
            for signal in discovery.get("signals", [])
            if signal not in {"site oficial", "evidencia publica"}
        ]
        enriched["status"] = "needs_website_review"
        return enriched

    collected = crawl_public_website_text(
        website_url,
        max_pages=4,
        max_chars_per_page=4500,
        max_total_chars=12000,
        require_brazilian_startup=False,
    )
    website_text = str(collected.get("text") or "")
    sector, signals = infer_sector_and_signals(
        " ".join(
            [
                str(discovery.get("article_title") or ""),
                str(discovery.get("description") or ""),
                website_text[:1400],
            ]
        ),
        source_label_from_url(str(discovery.get("source_url") or article_url)),
    )
    original_signals = [
        str(signal)
        for signal in discovery.get("signals", [])
        if str(signal).strip()
    ]
    merged_signals = []
    for signal in original_signals + signals + ["site oficial", "evidencia publica"]:
        if signal not in merged_signals:
            merged_signals.append(signal)

    excerpt = " ".join(website_text.split())[:900]
    enriched.update(
        {
            "website_url": collected.get("source_url") or website_url,
            "source_url": discovery.get("source_url") or article_url,
            "description": excerpt or discovery.get("description") or discovery.get("article_title") or "",
            "sector": sector if sector != "unknown" else discovery.get("sector") or "unknown",
            "signals": merged_signals,
            "confidence": min(95, max(int(discovery.get("confidence") or 0), 78)),
            "status": "enriched",
        }
    )
    return enriched


def enrich_discoveries(
    discoveries: list[dict[str, object]],
    max_items: int = 10,
) -> dict[str, object]:
    enriched = []
    failed = []
    candidates = [
        discovery
        for discovery in discoveries
        if str(discovery.get("status") or "") != "enriched"
    ][:max_items]

    for discovery in candidates:
        try:
            result = enrich_discovery_with_public_evidence(discovery)
            enriched.append(result)
        except requests.RequestException as error:
            failed.append({**discovery, "status": "enrichment_failed", "error": str(error)})

    return {
        "processed": len(candidates),
        "enriched": sum(1 for item in enriched if item.get("status") == "enriched"),
        "needs_review": sum(
            1 for item in enriched if item.get("status") == "needs_website_review"
        ),
        "failed": len(failed),
        "results": enriched + failed,
    }


def review_discovery_with_website(
    discovery: dict[str, object],
    website_url: str,
    *,
    sector: str | None = None,
    stage: str | None = None,
    description: str | None = None,
    signals: list[str] | None = None,
) -> dict[str, object]:
    updated = dict(discovery)
    updated["website_url"] = website_url
    if sector:
        updated["sector"] = sector
    if stage:
        updated["stage"] = stage
    if description:
        updated["description"] = description
    if signals:
        merged_signals = []
        for signal in list(discovery.get("signals") or []) + signals:
            clean_signal = str(signal).strip()
            if clean_signal and clean_signal not in merged_signals:
                merged_signals.append(clean_signal)
        updated["signals"] = merged_signals
    updated["status"] = "manual_review"
    return enrich_discovery_with_public_evidence(updated)


def discovery_key(item: dict[str, object]) -> str:
    return startup_name_key(item.get("startup_name"))


def read_discoveries(discovery_path: str) -> list[dict[str, object]]:
    path = resolve_source_path(discovery_path)
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {
                **row,
                "signals": [
                    signal.strip()
                    for signal in str(row.get("signals") or "").split(";")
                    if signal.strip()
                ],
                "confidence": int(row.get("confidence") or 0),
            }
            for row in csv.DictReader(file)
            if row.get("startup_name")
        ]


def write_discoveries(discovery_path: str, discoveries: list[dict[str, object]]) -> None:
    path = resolve_source_path(discovery_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DISCOVERY_FIELDS)
        writer.writeheader()
        for discovery in discoveries:
            row = {field: discovery.get(field, "") for field in DISCOVERY_FIELDS}
            row["signals"] = ";".join(str(signal) for signal in discovery.get("signals", []))
            writer.writerow(row)


def collect_news_discoveries(
    source_url: str,
    max_items: int = 20,
    source_label: str | None = None,
) -> list[dict[str, object]]:
    adapter = discovery_adapter_for_url(source_url, source_label=source_label)
    return adapter.collect(max_items=max_items)


def collect_startupi_discoveries(source_url: str, max_items: int = 20) -> list[dict[str, object]]:
    return collect_news_discoveries(source_url, max_items=max_items, source_label="startupi")


def collect_discoveries_from_sources(
    source_urls: list[str],
    max_items: int = 20,
) -> dict[str, object]:
    errors = []
    source_batches: list[list[dict[str, object]]] = []

    for source_url in source_urls:
        try:
            adapter = discovery_adapter_for_url(source_url)
            found = adapter.collect(max_items=max_items)
        except requests.RequestException as error:
            errors.append({"source_url": source_url, "error": str(error)})
            continue
        source_batches.append(found)

    discoveries = []
    seen: set[str] = set()
    for index in range(max_items):
        for batch in source_batches:
            if index >= len(batch):
                continue
            item = batch[index]
            key = discovery_key(item)
            if key in seen:
                continue
            seen.add(key)
            discoveries.append(item)
            if len(discoveries) >= max_items:
                return {"results": discoveries, "errors": errors}

    return {"results": discoveries, "errors": errors}


def refresh_discovery_repertoire(
    *,
    source_url: str,
    discovery_path: str,
    max_items: int = 20,
    source_urls: list[str] | None = None,
) -> dict[str, object]:
    existing = read_discoveries(discovery_path)
    existing_by_key = {discovery_key(item): item for item in existing}
    sources = source_urls or parse_discovery_source_urls(None, source_url)
    collection = collect_discoveries_from_sources(sources, max_items=max_items)
    found = list(collection["results"])

    added = 0
    for item in found:
        key = discovery_key(item)
        if key in existing_by_key:
            existing_by_key[key] = {**existing_by_key[key], **item, "status": "seen"}
            continue
        existing_by_key[key] = item
        added += 1

    discoveries = sorted(
        existing_by_key.values(),
        key=lambda item: str(item.get("discovered_at") or ""),
        reverse=True,
    )
    write_discoveries(discovery_path, discoveries)
    return {
        "source_url": ", ".join(sources),
        "found": len(found),
        "added": added,
        "total": len(discoveries),
        "results": discoveries[:max_items],
        "errors": collection["errors"],
    }


def use_discovered_startups(
    *,
    discovery_path: str,
    startup_source_path: str,
    min_confidence: int = 50,
) -> dict[str, object]:
    discoveries = read_discoveries(discovery_path)
    current = load_startup_candidates(startup_source_path)
    current_names = {normalize_text(candidate.get("startup_name")) for candidate in current}

    imported = []
    skipped = []
    for discovery in discoveries:
        name_key = normalize_text(discovery.get("startup_name"))
        if not name_key or name_key in current_names:
            skipped.append(discovery)
            continue
        if int(discovery.get("confidence") or 0) < min_confidence:
            skipped.append(discovery)
            continue

        candidate = {
            "startup_name": discovery["startup_name"],
            "country_code": "BR",
            "sector": discovery.get("sector") or "unknown",
            "stage": "",
            "source": "discovered_startupi",
            "website_url": "",
            "github_url": "",
            "source_url": discovery.get("article_url") or discovery.get("source_url") or "",
            "description": discovery.get("description") or discovery.get("article_title") or "",
            "signals": discovery.get("signals") or ["noticia", "startupi", "Brasil"],
        }
        current.append(candidate)
        current_names.add(name_key)
        imported.append(candidate)

    if imported:
        write_startup_candidates(startup_source_path, current)

    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "total_active": len(current),
        "results": imported,
    }
