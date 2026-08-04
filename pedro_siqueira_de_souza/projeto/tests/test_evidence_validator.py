"""Testes do Evidence Validator Agent — offline e SEM LLM (regras puras).

Cobrem as três regras de validação, a aresta condicional (`route_after_validation`)
com sua guarda de terminação, e o incremento do contador de tentativas.
"""
from langgraph.graph import END

from agents.evidence_validator import (
    LOW_RATIO_LIMIAR,
    MAX_ATTEMPTS,
    evidence_validator_node,
    route_after_validation,
)


def _classified(label="AI-native", confidence="high", ai_signals=None,
                extraction_basis="content", name="Salvy") -> dict:
    """ClassifiedStartup serializado, pronto pra entrar no estado."""
    return {
        "startup": {
            "name": name,
            "description": "Telefonia móvel para empresas.",
            "sector": "telecom",
            "stage": None,
            "funding": None,
            "tech_stack": ["Python"],
            "ai_signals": ai_signals if ai_signals is not None else ["ML próprio"],
            "extraction_basis": extraction_basis,
        },
        "label": label,
        "rationale": "justificativa qualquer",
        "confidence": confidence,
    }


# --- Regras de validação ----------------------------------------------------

def test_validator_herda_confianca_quando_consistente():
    out = evidence_validator_node({"classified_startups": [_classified(confidence="high")]})
    v = out["validated_startups"][0]

    assert v["validation_confidence"] == "high"   # herdou do classifier
    assert v["issues"] == []
    assert v["classified"]["startup"]["name"] == "Salvy"  # cadeia aninhada intacta


def test_validator_metadata_vira_low():
    out = evidence_validator_node({"classified_startups": [
        _classified(confidence="high", extraction_basis="metadata"),
    ]})
    v = out["validated_startups"][0]

    assert v["validation_confidence"] == "low"
    assert "sem conteúdo coletado" in v["issues"]


def test_validator_rotulo_de_ia_sem_sinais_vira_low():
    out = evidence_validator_node({"classified_startups": [
        _classified(label="AI-native", confidence="high", ai_signals=[]),
    ]})
    v = out["validated_startups"][0]

    assert v["validation_confidence"] == "low"
    assert "rótulo de IA sem sinais textuais" in v["issues"]


def test_validator_non_ai_sem_sinais_nao_e_inconsistente():
    # Non-AI sem sinais de IA é coerente: a regra de inconsistência não dispara.
    out = evidence_validator_node({"classified_startups": [
        _classified(label="Non-AI", confidence="medium", ai_signals=[]),
    ]})
    v = out["validated_startups"][0]

    assert v["validation_confidence"] == "medium"
    assert v["issues"] == []


def test_validator_incrementa_contador():
    out = evidence_validator_node({"classified_startups": [], "validation_attempts": 1})
    assert out["validation_attempts"] == 2


def test_validator_nao_muta_estado_original():
    original = _classified(extraction_basis="metadata")
    evidence_validator_node({"classified_startups": [original]})

    assert original["confidence"] == "high"      # não rebaixou o dict de entrada
    assert "validation_confidence" not in original


# --- Aresta condicional (roteamento) ----------------------------------------

def test_route_recoleta_quando_muitas_low_e_ha_orcamento():
    state = {
        "validated_startups": [
            {"validation_confidence": "low"},
            {"validation_confidence": "high"},
        ],  # fração low = 0.5 >= limiar
        "validation_attempts": 1,  # < MAX_ATTEMPTS
    }
    assert LOW_RATIO_LIMIAR == 0.5
    assert route_after_validation(state) == "scraper"


def test_route_para_quando_orcamento_esgotado():
    state = {
        "validated_startups": [{"validation_confidence": "low"}],  # 100% low
        "validation_attempts": MAX_ATTEMPTS,  # guarda de terminação atingida
    }
    assert route_after_validation(state) == END


def test_route_segue_quando_poucas_low():
    state = {
        "validated_startups": [
            {"validation_confidence": "high"},
            {"validation_confidence": "high"},
            {"validation_confidence": "low"},
        ],  # fração low = 1/3 < limiar
        "validation_attempts": 0,
    }
    assert route_after_validation(state) == END


def test_route_segue_quando_lista_vazia():
    assert route_after_validation({"validated_startups": [], "validation_attempts": 0}) == END
