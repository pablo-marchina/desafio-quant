"""Testes do Recommendation Agent — catálogo (regras) + LLM (narrativa).

As regras são offline/determinísticas (passamos `usar_llm=False`); a parte de
LLM é testada com um modelo falso (sem rede), no padrão do resto do projeto.
"""
from agents.recommendation import (
    _GrowthItem,
    _GrowthOutput,
    _recomendar,
    recommendation_node,
)


# --- LLM falso (mesma costura dos outros testes) --------------------------

class _FakeStructured:
    def __init__(self, out):
        self._out = out

    def invoke(self, _prompt):
        return self._out


class _FakeLLM:
    def __init__(self, out):
        self._out = out

    def with_structured_output(self, _schema):
        return _FakeStructured(self._out)


def _startup(name, **kw):
    base = {"name": name, "description": None, "sector": None,
            "ai_signals": [], "tech_stack": []}
    base.update(kw)
    return base


# --- regras puras (sem LLM) -----------------------------------------------

def test_recomendar_usa_catalogo_e_template_sem_llm():
    s = _startup("DataPay", sector="fintech",
                 description="plataforma de análise de dados financeiros com etl e pandas")
    rec = _recomendar("DataPay", "Non-AI", s, [], usar_llm=False)
    techs = [t.tech for t in rec.technologies]
    assert "NVIDIA RAPIDS" in techs          # produto de dado p/ empresa data-heavy
    rapids = next(t for t in rec.technologies if t.tech == "NVIDIA RAPIDS")
    assert rapids.growth                      # template do catálogo preenche
    assert any("Non-AI" in n for n in rec.notes)


def test_recomendar_sem_aderencia_retorna_vazio():
    s = _startup("Padaria", description="pães artesanais de bairro")
    rec = _recomendar("Padaria", "Non-AI", s, [], usar_llm=False)
    assert rec.technologies == []
    assert rec.notes and "nenhum produto" in rec.notes[0]


def test_recomendar_define_confianca_geral_pela_primeira():
    s = _startup("Voz", sector="Software/SaaS",
                 description="assistente de voz com llm para call center e transcrição")
    rec = _recomendar("Voz", "AI-native", s, [], usar_llm=False)
    assert rec.technologies                    # achou produtos aderentes
    assert rec.overall_confidence == rec.technologies[0].confidence


# --- híbrido com LLM ------------------------------------------------------

def test_recomendar_llm_escreve_growth(monkeypatch):
    out = _GrowthOutput(items=[
        _GrowthItem(tech="NVIDIA RAPIDS", growth="acelera seus ETLs financeiros em GPU")
    ])
    monkeypatch.setattr("agents.recommendation.get_llm", lambda: _FakeLLM(out))
    s = _startup("DataPay", sector="fintech", description="dados etl pandas")
    rec = _recomendar("DataPay", "Non-AI", s, [], usar_llm=True)
    rapids = next(t for t in rec.technologies if t.tech == "NVIDIA RAPIDS")
    assert rapids.growth == "acelera seus ETLs financeiros em GPU"  # LLM sobrescreve


def test_recomendar_llm_falha_cai_no_template(monkeypatch):
    class _Boom:
        def with_structured_output(self, _):
            raise RuntimeError("LLM fora do ar")
    monkeypatch.setattr("agents.recommendation.get_llm", lambda: _Boom())
    s = _startup("DataPay", sector="fintech", description="dados etl pandas")
    rec = _recomendar("DataPay", "Non-AI", s, [], usar_llm=True)
    rapids = next(t for t in rec.technologies if t.tech == "NVIDIA RAPIDS")
    assert rapids.growth  # template do catálogo, sem quebrar


# --- nó do grafo ----------------------------------------------------------

def _validated(name, label, startup=None):
    return {
        "classified": {
            "startup": startup or _startup(name),
            "label": label, "rationale": "x", "confidence": "high",
        },
        "validation_confidence": "high", "issues": [],
    }


def test_node_monta_recomendacoes(monkeypatch):
    monkeypatch.setattr("agents.recommendation.get_llm",
                        lambda: _FakeLLM(_GrowthOutput(items=[])))
    s = _startup("DataPay", sector="fintech", description="dados etl pandas")
    state = {
        "validated_startups": [_validated("DataPay", "Non-AI", s)],
        "rag_contexts": [{"name": "DataPay", "chunks": []}],
    }
    out = recommendation_node(state)
    rec = out["recommendations"][0]
    assert rec["name"] == "DataPay"
    assert any(t["tech"] == "NVIDIA RAPIDS" for t in rec["technologies"])
    assert "1/1" in out["messages"][0][1]


def test_node_sem_validadas_nao_quebra():
    out = recommendation_node({"validated_startups": [], "rag_contexts": []})
    assert out["recommendations"] == []
