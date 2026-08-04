"""Testes da persistência — só a lógica PURA (sem banco).

`rows_from_state` mapeia o estado final do grafo para as linhas da tabela
`startups`. As funções que tocam o Postgres (save/list) são validadas
manualmente contra o Supabase, não em testes unitários offline.
"""
from database.repo import rows_from_state


def _state():
    return {
        "query": "fintechs de IA",
        "classified_startups": [
            {"startup": {"name": "ChatJurix", "sector": "legaltech",
                         "stage": "seed", "funding": "R$ 3M"},
             "label": "AI-native", "rationale": "x", "confidence": "high"},
            {"startup": {"name": "LogiBox", "sector": "logtech",
                         "stage": None, "funding": None},
             "label": "Non-AI", "rationale": "x", "confidence": "low"},
        ],
    }


def test_rows_from_state_junta_classificacao():
    rows = rows_from_state(_state())
    chat = next(r for r in rows if r["name"] == "ChatJurix")

    assert chat["classification"] == "AI-native"
    assert chat["sector"] == "legaltech"
    assert chat["confidence"] == 1.0  # high -> 1.0


def test_rows_from_state_mapeia_confianca_para_numerico():
    rows = rows_from_state(_state())
    logi = next(r for r in rows if r["name"] == "LogiBox")
    assert logi["confidence"] == 0.2  # low -> 0.2


def test_rows_from_state_inclui_detalhe_para_o_dropdown():
    state = {
        "classified_startups": [
            {"startup": {"name": "ChatJurix", "sector": "legaltech",
                         "description": "assistente jurídico com LLM"},
             "label": "AI-native", "rationale": "x", "confidence": "high"},
        ],
        "recommendations": [
            {"name": "ChatJurix", "label": "AI-native",
             "technologies": [{"tech": "NVIDIA NIM"}],
             "overall_confidence": "high", "notes": []},
        ],
        "briefings": [{"name": "ChatJurix", "label": "AI-native",
                       "markdown": "# Briefing — ChatJurix"}],
    }
    row = rows_from_state(state)[0]
    assert row["description"] == "assistente jurídico com LLM"
    assert row["recommendations"]["technologies"][0]["tech"] == "NVIDIA NIM"
    assert row["briefing"].startswith("# Briefing")


def test_rows_from_state_sem_detalhe_fica_none():
    # Sem recommendations/briefings no estado, os campos do dropdown ficam nulos.
    row = rows_from_state(_state())[0]
    assert row["recommendations"] is None
    assert row["briefing"] is None


def test_rows_from_state_vazio():
    assert rows_from_state({}) == []
