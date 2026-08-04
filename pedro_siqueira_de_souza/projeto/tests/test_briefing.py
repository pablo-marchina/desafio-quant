"""Testes do Briefing Agent — briefing CURTO e determinístico (≤2 parágrafos)."""
from agents.briefing import _render_briefing, briefing_node


def _validated(name, label="AI-native", **startup_fields):
    startup = {
        "name": name, "description": "assistente jurídico com LLM próprio",
        "sector": "legaltech", "stage": "seed", "funding": "R$ 2M",
        "tech_stack": ["Python"], "ai_signals": ["LLM próprio"],
        "extraction_basis": "content",
    }
    startup.update(startup_fields)
    return {
        "classified": {
            "startup": startup, "label": label,
            "rationale": "usa LLM próprio como núcleo", "confidence": "high",
        },
        "validation_confidence": "high", "issues": [],
    }


def _rec(name, label="AI-native", techs=None, overall="medium", notes=None):
    return {
        "name": name, "label": label,
        "technologies": techs if techs is not None else [{
            "tech": "NeMo Guardrails", "url": "https://nv/guardrails",
            "summary": "segurança e conformidade para apps com LLM",
            "confidence": "medium",
            "matched_signals": ["jurídic", "compliance"],
            "growth": "reduz risco regulatório ao operar LLMs",
            "snippet": "rails de segurança para LLMs",
        }],
        "overall_confidence": overall, "notes": notes or [],
    }


def test_briefing_tem_no_maximo_dois_paragrafos():
    md = _render_briefing(_rec("ChatJurix"), _validated("ChatJurix"))
    paragrafos = [p for p in md.split("\n\n") if p.strip()]
    assert len(paragrafos) <= 2


def test_briefing_traz_empresa_diagnostico_e_recomendacao():
    md = _render_briefing(_rec("ChatJurix"), _validated("ChatJurix"))
    assert "ChatJurix" in md
    assert "AI-native" in md             # diagnóstico
    assert "NeMo Guardrails" in md       # produto recomendado
    assert "risco regulatório" in md     # como ajuda a crescer


def test_briefing_cita_no_maximo_dois_produtos():
    techs = [
        {"tech": f"Prod{i}", "url": "u", "summary": "s",
         "confidence": "high", "matched_signals": [],
         "growth": f"ajuda {i}", "snippet": ""}
        for i in range(4)
    ]
    md = _render_briefing(_rec("Multi", techs=techs), _validated("Multi"))
    assert "Prod0" in md and "Prod1" in md       # os 2 primeiros
    assert "Prod2" not in md and "Prod3" not in md  # cortados (briefing curto)


def test_briefing_sem_tecnologias_avisa():
    md = _render_briefing(_rec("Vazia", techs=[]), _validated("Vazia"))
    assert "Nenhum produto NVIDIA" in md


def test_briefing_inclui_notas_da_recomendacao():
    rec = _rec("Padaria", label="Non-AI", overall="low",
               notes=["priorize produtos de dado/infra"])
    md = _render_briefing(rec, _validated("Padaria", label="Non-AI"))
    assert "produtos de dado/infra" in md  # a nota entra no briefing (capitalizada)


def test_briefing_sem_validated_nao_quebra():
    md = _render_briefing(_rec("Fantasma"), None)
    assert "Fantasma" in md
    assert "AI-native" in md  # ainda traz o diagnóstico mínimo


def test_briefing_node_gera_um_relatorio_por_recomendacao():
    state = {
        "validated_startups": [_validated("ChatJurix"), _validated("Aegro")],
        "recommendations": [_rec("ChatJurix"), _rec("Aegro")],
    }
    out = briefing_node(state)
    assert len(out["briefings"]) == 2
    nomes = {b["name"] for b in out["briefings"]}
    assert nomes == {"ChatJurix", "Aegro"}
    assert all("markdown" in b and b["markdown"] for b in out["briefings"])
    assert "2 relatórios" in out["messages"][0][1]


def test_briefing_node_sem_recomendacoes_nao_quebra():
    out = briefing_node({"validated_startups": [], "recommendations": []})
    assert out["briefings"] == []
