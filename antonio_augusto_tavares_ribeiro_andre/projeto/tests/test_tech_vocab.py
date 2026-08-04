"""Vocabulário controlado de tech (F5.11) — normalização determinística das tags do filtro."""

from __future__ import annotations

import pytest

from packages.schemas.tech_vocab import normalize_tech, normalize_techs, tech_matches


@pytest.mark.parametrize(
    ("raw", "tag"),
    [
        ("NVIDIA NIM", "NIM"),  # tira o prefixo de fornecedor
        ("nim", "NIM"),  # apelido em caixa baixa
        ("NeMo Retriever (RAG)", "NeMo Retriever"),  # tira o qualificador entre parênteses
        ("NVIDIA Riva (ASR/TTS)", "Riva"),
        ("NVIDIA Triton Inference Server", "Triton"),  # apelido funde a forma longa
        ("lang chain", "LangChain"),
        ("  PyTorch  ", "PyTorch"),  # colapsa espaços
        ("Acme SDK", "Acme SDK"),  # fora do mapa: volta limpo, preservando grafia
        ("NVIDIA", ""),  # só prefixo -> vazio (o caller descarta)
        ("", ""),
    ],
)
def test_normalize_tech(raw: str, tag: str) -> None:
    assert normalize_tech(raw) == tag


def test_normalize_tech_is_idempotent() -> None:
    for raw in ["NVIDIA NIM", "NeMo Retriever (RAG)", "lang chain", "Acme SDK"]:
        once = normalize_tech(raw)
        assert normalize_tech(once) == once


def test_normalize_techs_dedups_and_accepts_dicts() -> None:
    # Aceita o formato JSON de Company.tecnologias ({nome}) e strings; dedup case-insensitive.
    raw = [{"nome": "LangChain"}, "lang chain", {"nome": ""}, "NVIDIA NIM", "nim"]
    assert normalize_techs(raw) == ["LangChain", "NIM"]


def test_tech_matches_is_exact_on_normalized_tag() -> None:
    haystack = ["NeMo Retriever", "NIM"]
    assert tech_matches(None, haystack) is True  # sem filtro
    assert tech_matches("nvidia nim", haystack) is True  # grafia diferente, mesma tag
    assert tech_matches("NeMo", haystack) is False  # não casa substring de "NeMo Retriever"
