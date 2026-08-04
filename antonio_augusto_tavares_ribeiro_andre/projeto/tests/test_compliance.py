"""Testes da compliance de coleta: robots + rate limit + quota + UA (F1.8).

Tudo roda **offline**: o robots.txt vem de um fetcher em memória (sem rede), o rate
limiter usa relógio e `sleep` falsos (não dorme de verdade) e a guarda de quota é pura
aritmética. Provam as quatro garantias do DoD do F1 sem chave nem rede.
"""

from __future__ import annotations

import pytest

from packages.scraping.compliance import (
    USER_AGENT,
    USER_AGENT_TOKEN,
    ComplianceGate,
    QuotaExceeded,
    QuotaGuard,
    RateLimiter,
    RobotsCache,
    RobotsDisallowed,
)

_ROBOTS_BLOCKS_PRIVATE = """
User-agent: *
Disallow: /private/
"""


def _robots_from(mapping: dict[str, str]):
    """Fetcher de robots em memória: host → texto do robots.txt (None se ausente)."""
    seen: list[str] = []

    def fetcher(robots_url: str) -> str | None:
        seen.append(robots_url)
        for host, text in mapping.items():
            if host in robots_url:
                return text
        return None

    fetcher.seen = seen  # type: ignore[attr-defined]
    return fetcher


# --- user-agent ----------------------------------------------------------------


def test_user_agent_is_identifiable() -> None:
    # diz o produto, a URL de contato e a finalidade (compliance F1.8).
    assert USER_AGENT_TOKEN == "TAPI-bot"
    assert "http" in USER_AGENT  # URL de contato
    assert "coleta de dados públicos" in USER_AGENT


def test_adapters_share_the_central_user_agent() -> None:
    # F1.8 centraliza o UA: cada adapter (F1.2–F1.6) reexporta o mesmo valor.
    from packages.scraping import article, crawler, dynamic, soup

    for module in (article, crawler, dynamic, soup):
        assert module.DEFAULT_USER_AGENT is USER_AGENT


# --- robots.txt ----------------------------------------------------------------


def test_robots_blocks_disallowed_path() -> None:
    cache = RobotsCache(fetcher=_robots_from({"news.example": _ROBOTS_BLOCKS_PRIVATE}))
    assert cache.allowed("https://news.example/posts/ai") is True
    assert cache.allowed("https://news.example/private/secret") is False


def test_robots_absent_allows_everything() -> None:
    # robots ausente (fetcher devolve None) → convenção: permite tudo.
    cache = RobotsCache(fetcher=lambda _: None)
    assert cache.allowed("https://x.example/qualquer/coisa") is True


def test_robots_cached_per_host() -> None:
    fetcher = _robots_from({"x.example": "User-agent: *\nDisallow:\n"})
    cache = RobotsCache(fetcher=fetcher)
    cache.allowed("https://x.example/a")
    cache.allowed("https://x.example/b")
    cache.allowed("https://x.example/c")
    assert len(fetcher.seen) == 1  # robots baixado uma única vez por host


def test_robots_rejects_url_without_host() -> None:
    cache = RobotsCache(fetcher=lambda _: None)
    with pytest.raises(ValueError):
        cache.allowed("/sem/host")


# --- rate limit ----------------------------------------------------------------


def _fake_clock(times: list[float]):
    """Relógio determinístico: devolve os instantes da lista em sequência."""
    it = iter(times)
    return lambda: next(it)


def test_rate_limiter_sleeps_only_remaining_delay() -> None:
    slept: list[float] = []
    # 1ª chamada em t=0 (sem espera); 2ª em t=0.4 → falta 0.6 do delay de 1.0.
    limiter = RateLimiter(delay=1.0, clock=_fake_clock([0.0, 0.4]), sleep=slept.append)
    assert limiter.wait("https://x.example/a") == 0.0  # primeira: sem atraso
    assert limiter.wait("https://x.example/b") == pytest.approx(0.6)
    assert slept == [pytest.approx(0.6)]


def test_rate_limiter_is_per_host() -> None:
    slept: list[float] = []
    # dois hosts diferentes em t=0 e t=0.1: nenhum espera (contadores separados).
    limiter = RateLimiter(delay=1.0, clock=_fake_clock([0.0, 0.1]), sleep=slept.append)
    assert limiter.wait("https://a.example/x") == 0.0
    assert limiter.wait("https://b.example/y") == 0.0
    assert slept == []


# --- guarda de quota -----------------------------------------------------------


def test_quota_guard_charges_and_tracks() -> None:
    guard = QuotaGuard(limits={"tavily": 3})
    assert guard.charge("tavily") == 1
    assert guard.charge("tavily", 2) == 3
    assert guard.used("tavily") == 3
    assert guard.remaining("tavily") == 0


def test_quota_guard_raises_before_overrun() -> None:
    guard = QuotaGuard(limits={"firecrawl": 2})
    guard.charge("firecrawl", 2)
    with pytest.raises(QuotaExceeded) as exc:
        guard.charge("firecrawl")  # 3ª passaria do teto 2
    assert exc.value.resource == "firecrawl"
    assert exc.value.limit == 2
    assert guard.used("firecrawl") == 2  # cobrança que estoura não conta


def test_quota_guard_unlimited_when_no_limit() -> None:
    guard = QuotaGuard()  # sem tetos → ilimitado, só contabiliza
    for _ in range(100):
        guard.charge("tavily")
    assert guard.used("tavily") == 100
    assert guard.remaining("tavily") is None


# --- portão unificado ----------------------------------------------------------


def test_gate_blocks_on_robots_before_charging_quota() -> None:
    quota = QuotaGuard(limits={"firecrawl": 5})
    gate = ComplianceGate(
        robots=RobotsCache(fetcher=_robots_from({"x.example": _ROBOTS_BLOCKS_PRIVATE})),
        quota=quota,
        rate_limiter=RateLimiter(clock=_fake_clock([0.0]), sleep=lambda _: None),
    )
    with pytest.raises(RobotsDisallowed):
        gate.check("https://x.example/private/x", resource="firecrawl")
    assert quota.used("firecrawl") == 0  # URL barrada não consome quota


def test_gate_charges_quota_and_rate_limits_when_allowed() -> None:
    slept: list[float] = []
    quota = QuotaGuard(limits={"firecrawl": 5})
    gate = ComplianceGate(
        robots=RobotsCache(fetcher=lambda _: None),
        quota=quota,
        rate_limiter=RateLimiter(delay=1.0, clock=_fake_clock([0.0, 0.2]), sleep=slept.append),
    )
    gate.check("https://x.example/a", resource="firecrawl")
    gate.check("https://x.example/b", resource="firecrawl")
    assert quota.used("firecrawl") == 2
    assert slept == [pytest.approx(0.8)]  # 2ª chamada respeitou o rate limit


def test_gate_skips_quota_when_resource_none() -> None:
    quota = QuotaGuard(limits={"firecrawl": 0})  # teto zero
    gate = ComplianceGate(
        robots=RobotsCache(fetcher=lambda _: None),
        quota=quota,
        rate_limiter=RateLimiter(clock=_fake_clock([0.0]), sleep=lambda _: None),
    )
    gate.check("https://x.example/a")  # resource=None → não cobra (HTTP direto)
    assert quota.used("firecrawl") == 0
