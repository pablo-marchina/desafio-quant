"""Testes da guarda LGPD de founder (F1.13).

Tudo offline/puro (regex sobre texto). Cobre o scanner de dado sensível/pessoal, a
redação do `background` e a política de `sanitize_founder` (descartar com sensível no
núcleo, redigir o texto livre, preservar a identidade profissional).
"""

from __future__ import annotations

import pytest

from packages.schemas.enums import LegalBasis
from packages.schemas.profile import Founder
from packages.scraping import (
    FOUNDER_LEGAL_BASIS,
    redact,
    sanitize_founder,
    scan_sensitive,
)
from packages.scraping.lgpd import REDACTION

# --- scanner ------------------------------------------------------------------


def test_scan_empty_or_none() -> None:
    assert scan_sensitive(None) == ()
    assert scan_sensitive("") == ()


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("histórico de depressão", "saude"),
        ("é evangélico praticante", "religiao"),
        ("filiação partidária ao centro", "politica"),
        ("declara origem racial indígena", "raca_etnia"),
        ("sobre sua orientação sexual", "orientacao_sexual"),
        ("filiado ao sindicato dos engenheiros", "sindical"),
        ("coleta de impressão digital", "biometrico_genetico"),
        ("CPF 123.456.789-09", "cpf"),
        ("contato (11) 98888-7777", "contato_pessoal"),
        ("e-mail joao@gmail.com", "contato_pessoal"),
        ("CEP 01310-100", "contato_pessoal"),
        ("casado e pai de dois", "vida_pessoal"),
        ("32 anos de idade", "vida_pessoal"),
    ],
)
def test_scan_detects_each_category(text: str, category: str) -> None:
    cats = {h.category for h in scan_sensitive(text)}
    assert category in cats


def test_scan_no_false_positive_on_professional_bio() -> None:
    bio = "CTO com 20 anos de experiência; ex-Google; mestre em Ciência da Computação na USP."
    assert scan_sensitive(bio) == ()


# --- redação ------------------------------------------------------------------


def test_redact_replaces_sensitive_keeps_rest() -> None:
    cleaned, hits = redact("Engenheiro sênior. CPF 111.444.777-35. Atua em fintech.")
    assert REDACTION in cleaned
    assert "Engenheiro sênior" in cleaned and "fintech" in cleaned
    assert "111.444.777-35" not in cleaned
    assert {h.category for h in hits} == {"cpf"}


def test_redact_clean_text_is_unchanged() -> None:
    text = "Cofundador e CEO; lidera produto e engenharia."
    cleaned, hits = redact(text)
    assert cleaned == text and hits == ()


# --- política de sanitize_founder --------------------------------------------


def test_founder_legal_basis_is_legitimate_interest() -> None:
    assert FOUNDER_LEGAL_BASIS is LegalBasis.LEGITIMO_INTERESSE


def test_clean_founder_passes_through_unchanged() -> None:
    f = Founder(nome="Jane Doe", cargo="CEO", background="Ex-Google, formada em CS.")
    r = sanitize_founder(f)
    assert r.kept and not r.dropped and r.removed == ()
    assert r.founder is f  # sem mudança → mesma instância
    assert r.legal_basis is LegalBasis.LEGITIMO_INTERESSE


def test_background_is_redacted_but_founder_kept() -> None:
    f = Founder(
        nome="João Silva",
        cargo="CTO",
        linkedin_url="https://linkedin.com/in/joaosilva",
        background="Casado, 45 anos de idade. Líder técnico há 15 anos em SaaS.",
    )
    r = sanitize_founder(f)
    assert r.kept
    assert REDACTION in r.founder.background
    assert "Líder técnico" in r.founder.background  # narrativa profissional preservada
    assert str(r.founder.linkedin_url).endswith("joaosilva")  # perfil público mantido
    assert {h.category for h in r.removed} == {"vida_pessoal"}


def test_sensitive_in_core_drops_founder() -> None:
    r = sanitize_founder(Founder(nome="Maria", cargo="Diretora (HIV+)"))
    assert not r.kept and r.dropped
    assert r.founder is None
    assert r.removed  # registra o que motivou o descarte


def test_background_all_sensitive_becomes_none() -> None:
    f = Founder(nome="Ana", cargo="COO", background="Casada. 38 anos de idade. Católica.")
    r = sanitize_founder(f)
    assert r.kept and r.founder.background is None  # sobrou só marcador → zera
    assert len(r.removed) >= 2
