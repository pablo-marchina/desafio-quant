"""Testes das seed lists de fontes do §9 (F0.9).

Garantem que os YAMLs de `data/seeds/` carregam num modelo válido, que a política de
coleta (allowlist/denylist, F1.15) é consistente — diretórios §9.1 não são `allow`,
notícias §9.2 são a fonte primária `allow` — e que os helpers de consulta funcionam.
"""

from __future__ import annotations

from packages.scraping import allowlist, by_type, denylist, load_sources


def test_loads_nonempty_with_unique_ids() -> None:
    sources = load_sources()
    assert len(sources) >= 10
    ids = [s.id for s in sources]
    assert len(ids) == len(set(ids))  # IDs únicos (o loader também valida)


def test_every_source_is_well_formed() -> None:
    for s in load_sources():
        assert s.url.startswith("http")
        assert s.type in {"directory", "news", "program"}
        assert s.policy in {"allow", "api_only", "deny"}
        assert s.country in {"BR", "GLOBAL"}
        assert s.legal_basis  # base de coleta sempre declarada


def test_policy_consistency_allow_not_prohibited() -> None:
    # F1.15: nada marcado allow pode ter ToS proibindo scraping.
    for s in load_sources():
        if s.policy == "allow":
            assert s.tos_scraping != "prohibited"
            assert s.collectable is True


def test_directories_are_not_directly_collectable() -> None:
    # §9.1 (plataformas proprietárias) nunca entram na allowlist.
    dirs = by_type("directory")
    assert dirs
    assert all(s.policy in {"api_only", "deny"} for s in dirs)


def test_news_are_primary_allowlist() -> None:
    # §9.2 é a fonte primária de coleta (F1.15) → todas allow.
    news = by_type("news")
    assert news
    assert all(s.policy == "allow" for s in news)


def test_allow_and_deny_partition() -> None:
    total = len(load_sources())
    assert len(allowlist()) + len(denylist()) == total
    assert allowlist() and denylist()  # ambos não-vazios
