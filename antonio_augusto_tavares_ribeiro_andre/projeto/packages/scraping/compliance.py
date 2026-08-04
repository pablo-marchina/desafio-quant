"""Compliance de coleta: robots.txt + rate limit + user-agent + guarda de quota (F1.8).

Os adapters de página única (Firecrawl F1.2, Playwright F1.3, trafilatura F1.4, bs4 F1.5),
orquestrados pelo roteador (F1.7), **não** passam pelo Scrapy — então a compliance que o
crawler (F1.6) ganha de graça via settings do Scrapy (`ROBOTSTXT_OBEY`/`DOWNLOAD_DELAY`/UA)
precisa de um guardião explícito para o caminho do roteador. Este módulo é esse guardião e a
**fonte única** das quatro garantias prometidas no DoD do F1 ("respeita robots.txt; nenhuma
fonte fechada"):

- **user-agent identificável** (`USER_AGENT`): quem somos / como contatar, num só lugar —
  antes cada adapter (F1.2–F1.6) declarava a sua cópia; agora todos importam daqui.
- **robots.txt** (`RobotsCache`): consulta o robots do host (cacheado por host) e diz se a
  URL é coletável para o nosso UA. Convenção padrão: robots ausente/ilegível → **permite**;
  só um `Disallow` explícito barra. O fetcher de robots é injetável → testável offline.
- **rate limit** (`RateLimiter`): impõe um atraso mínimo por host entre requisições. Relógio
  (`monotonic`) e `sleep` injetáveis → os testes não dormem de verdade.
- **guarda de quota de free tier** (`QuotaGuard`): contador por recurso (tavily/firecrawl)
  com teto por run; estoura `QuotaExceeded` **antes** da chamada que passaria do limite — o
  free tier não vaza silenciosamente. Espelha a guarda de orçamento de LLM (F2.11).

O `ComplianceGate` junta os três no portão único que o caller do roteador usa por fetch:
`gate.check(url, "firecrawl")` verifica robots → cobra a quota → respeita o rate limit,
**nessa ordem** (barra antes de gastar). Tudo é puro/injetável: nenhuma rede nos testes.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

# User-agent identificável (compliance F1.8): fonte ÚNICA de quem somos e como contatar.
# Compartilhado por todos os adapters de coleta (F1.2–F1.6) — diz o produto, a URL de
# contato e a finalidade, para que um operador de site saiba quem está coletando.
USER_AGENT = (
    "TAPI-bot/0.1 (+https://github.com/antonioatra/case_NVIDIA; "
    "NVIDIA Startup AI Radar; coleta de dados públicos)"
)

# Token de produto do UA (antes da "/") — é o que o `User-agent:` do robots.txt casa.
USER_AGENT_TOKEN = USER_AGENT.split("/", 1)[0]  # "TAPI-bot"

# Tetos conservadores de free tier por run (Tavily/Firecrawl). O caller ajusta conforme
# o plano contratado; o ponto é ter um limite explícito em vez de estourar em silêncio.
DEFAULT_QUOTA_LIMITS: dict[str, int] = {"tavily": 50, "firecrawl": 50}

# Fetcher de robots.txt: dada a URL do robots, devolve o texto ou None se indisponível.
RobotsFetcher = Callable[[str], "str | None"]


class ComplianceError(RuntimeError):
    """Base das violações de compliance de coleta (F1.8)."""


class RobotsDisallowed(ComplianceError):
    """Levantada quando o robots.txt do host proíbe coletar a URL para o nosso UA."""

    def __init__(self, url: str) -> None:
        super().__init__(f"robots.txt proíbe coletar {url!r} para {USER_AGENT_TOKEN} (F1.8)")
        self.url = url


class QuotaExceeded(ComplianceError):
    """Levantada quando uma cobrança passaria do teto de free tier do recurso no run."""

    def __init__(self, resource: str, limit: int) -> None:
        super().__init__(
            f"quota de free tier estourada para {resource!r}: teto {limit} por run (F1.8)"
        )
        self.resource = resource
        self.limit = limit


def _default_robots_fetcher(robots_url: str) -> str | None:
    """Baixa o robots.txt do host com o nosso UA; None em 4xx/erro (→ libera tudo)."""
    from urllib.request import Request, urlopen

    request = Request(robots_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 (robots do host alvo)
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        # robots ausente (404), bloqueado ou rede caiu → convenção: permitir (sem regra).
        return None


def _origin(url: str) -> tuple[str, str]:
    """(scheme, netloc) de uma URL; levanta `ValueError` se faltar esquema/host."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"url sem esquema/host: {url!r}")
    return parts.scheme, parts.netloc.lower()


@dataclass
class RobotsCache:
    """Cache por host das regras de robots.txt; diz se uma URL é coletável (F1.8).

    Convenção padrão: robots ausente/ilegível (4xx, erro de rede) → **permite** tudo;
    só uma regra `Disallow` explícita barra. O `fetcher` é injetável → testes passam
    um robots.txt em memória, sem tocar a rede. Um host visto uma vez fica cacheado
    pelo run inteiro (não rebaixa o robots a cada URL do mesmo domínio).
    """

    fetcher: RobotsFetcher = _default_robots_fetcher
    user_agent: str = USER_AGENT_TOKEN
    _parsers: dict[tuple[str, str], RobotFileParser | None] = field(default_factory=dict)

    def _parser_for(self, url: str) -> RobotFileParser | None:
        origin = _origin(url)
        if origin not in self._parsers:
            robots_url = urlunsplit((origin[0], origin[1], "/robots.txt", "", ""))
            text = self.fetcher(robots_url)
            if text is None:
                self._parsers[origin] = None  # sem robots → libera tudo
            else:
                parser = RobotFileParser()
                parser.parse(text.splitlines())
                self._parsers[origin] = parser
        return self._parsers[origin]

    def allowed(self, url: str) -> bool:
        """True se o robots do host permite coletar `url` para o nosso UA."""
        parser = self._parser_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)


@dataclass
class RateLimiter:
    """Atraso mínimo por host entre requisições (rate limit, F1.8).

    Mantém, por host, o instante em que o **próximo** fetch é permitido. `wait(url)`
    dorme só o necessário e devolve quanto dormiu. Relógio (`clock`) e `sleep` são
    injetáveis para os testes verificarem a espera sem dormir de verdade.
    """

    delay: float = 1.0
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _next_allowed: dict[str, float] = field(default_factory=dict)

    def wait(self, url: str) -> float:
        """Espera o atraso pendente para o host de `url`; devolve os segundos dormidos."""
        host = urlsplit(url).netloc.lower()
        now = self.clock()
        earliest = self._next_allowed.get(host, now)
        slept = max(0.0, earliest - now)
        if slept > 0:
            self.sleep(slept)
        # Próximo fetch deste host só a partir de agora (ou do horário pendente) + delay.
        self._next_allowed[host] = max(now, earliest) + self.delay
        return slept


@dataclass
class QuotaGuard:
    """Contador de chamadas de free tier por recurso, com teto por run (F1.8).

    Espelha a guarda de orçamento de LLM (F2.11): cobra **antes** da chamada e estoura
    `QuotaExceeded` quando a cobrança passaria do teto — o free tier (Tavily/Firecrawl)
    não vaza silenciosamente num run grande (cohort builder, F1.14). Recurso sem teto
    configurado é ilimitado (apenas contabilizado, para observabilidade).
    """

    limits: dict[str, int] = field(default_factory=dict)
    _used: dict[str, int] = field(default_factory=dict)

    def charge(self, resource: str, n: int = 1) -> int:
        """Cobra `n` chamadas do recurso; estoura se passar do teto. Devolve o total usado."""
        if n < 0:
            raise ValueError("n não pode ser negativo")
        used = self._used.get(resource, 0)
        limit = self.limits.get(resource)
        if limit is not None and used + n > limit:
            raise QuotaExceeded(resource, limit)
        self._used[resource] = used + n
        return self._used[resource]

    def used(self, resource: str) -> int:
        """Chamadas já gastas do recurso neste run."""
        return self._used.get(resource, 0)

    def remaining(self, resource: str) -> int | None:
        """Chamadas restantes até o teto; None se o recurso é ilimitado."""
        limit = self.limits.get(resource)
        if limit is None:
            return None
        return max(0, limit - self._used.get(resource, 0))


@dataclass
class ComplianceGate:
    """Portão único de compliance antes de cada fetch do roteador (F1.8).

    `check(url, resource)` na ordem **robots → quota → rate limit**: barra antes de
    gastar. Uma URL proibida pelo robots não consome quota; uma quota estourada não
    dorme no rate limit. `resource=None` para fetches sem quota de free tier (HTTP
    direto via trafilatura/bs4/Playwright); `"tavily"`/`"firecrawl"` para os pagos.
    """

    robots: RobotsCache = field(default_factory=RobotsCache)
    quota: QuotaGuard = field(default_factory=lambda: QuotaGuard(dict(DEFAULT_QUOTA_LIMITS)))
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)

    def check(self, url: str, resource: str | None = None) -> None:
        """Aplica robots + quota + rate limit para `url`; levanta se algo proíbe."""
        if not self.robots.allowed(url):
            raise RobotsDisallowed(url)
        if resource is not None:
            self.quota.charge(resource)
        self.rate_limiter.wait(url)
