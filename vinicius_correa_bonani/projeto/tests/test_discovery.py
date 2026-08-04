"""Testes da descoberta (offline — busca/scrape/LLM monkeypatchados)."""

from app import discovery


def test_descobrir_dedup_e_limita(monkeypatch):
    monkeypatch.setattr(discovery, "_coletar_texto", lambda tema, top_n=5: "texto com empresas")
    # LLM devolve nomes com duplicata (case-insensitive) e um vazio
    monkeypatch.setattr(
        discovery, "extrair_nomes",
        lambda texto: ["Tractian", "tractian", "Gupy", "  ", "iFood", "Dr. Consulta"],
    )
    nomes = discovery.descobrir("saúde", n=3)
    assert nomes == ["Tractian", "Gupy", "iFood"]   # dedup + sem vazio + limite n=3


def test_descobrir_sem_texto_retorna_vazio(monkeypatch):
    # _coletar_texto não achou nada → extrair_nomes (real) tem guarda p/ texto vazio → []
    monkeypatch.setattr(discovery, "_coletar_texto", lambda tema, top_n=5: "")
    assert discovery.descobrir("tema inexistente") == []
