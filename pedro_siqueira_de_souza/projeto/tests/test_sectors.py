"""Testes da taxonomia canônica de setores (core/sectors.py)."""
from core.sectors import OUTROS, bucket_sectors, canonical_sector


def test_mapeia_jargoes_para_nomes_concretos():
    assert canonical_sector("agtech") == "Agronegócio"
    assert canonical_sector("fintech") == "Finanças"
    assert canonical_sector("healthtech") == "Saúde"


def test_variantes_do_mesmo_ramo_caem_no_mesmo_bucket():
    # "fintech" e "finanças" devem virar UM setor só, não dois.
    assert canonical_sector("fintech") == canonical_sector("Finanças")


def test_case_insensitive_e_com_espacos():
    assert canonical_sector("  AgTech  ") == "Agronegócio"


def test_nulo_e_vazio_viram_outros():
    assert canonical_sector(None) == OUTROS
    assert canonical_sector("") == OUTROS
    assert canonical_sector("   ") == OUTROS


def test_desconhecido_vira_outros():
    assert canonical_sector("setor inexistente xyz") == OUTROS


def test_bucket_soma_variantes_e_ordena_desc():
    raw = [
        {"sector": "fintech", "count": 3},
        {"sector": "finanças", "count": 2},   # mesmo bucket de fintech
        {"sector": "agtech", "count": 4},
        {"sector": None, "count": 1},           # -> Outros
    ]
    out = bucket_sectors(raw)
    nomes = [d["sector"] for d in out]
    counts = {d["sector"]: d["count"] for d in out}

    assert counts["Finanças"] == 5            # 3 + 2 somados
    assert counts["Agronegócio"] == 4
    assert counts[OUTROS] == 1
    assert nomes == sorted(nomes, key=lambda n: counts[n], reverse=True)


def test_bucket_respeita_o_limite():
    raw = [{"sector": s, "count": 1} for s in
           ("fintech", "healthtech", "agtech", "varejo", "edtech")]
    assert len(bucket_sectors(raw, limit=2)) == 2
