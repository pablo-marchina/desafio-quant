"""Testes do Evidence Validator (grounding — LLM monkeypatchado).

O nó agora faz faithfulness check por LLM (`verificar_afirmacoes`). Os testes
monkeypatcham essa função (como test_classifier faz com `classificar`) e mantêm
uma chave LLM fake, para exercitar o caminho de grounding sem rede. O pré-gate
estrutural (≥3 domínios + campos) e o teto do loop (`tentativas`) seguem determinísticos.
"""

import pytest

from app import evidence_validator as ev
from app.state import DadosEmpresa, RadarState, VerificacaoAfirmacao


@pytest.fixture(autouse=True)
def grounding_ligado(monkeypatch):
    """Por padrão: grounding ligado e chave LLM presente (caminho de faithfulness)."""
    monkeypatch.setattr(ev.settings, "grounding_habilitado", True)
    monkeypatch.setattr(ev.settings, "groq_api_key", "fake-key")


def _state(fontes, setor="Indústria", descricao="faz X", tentativas=0, **extra):
    return RadarState(
        conteudo_bruto=[{"texto": "t", "fonte": f} for f in fontes],
        dados_estruturados=DadosEmpresa(nome="X", setor=setor, descricao=descricao, **extra),
        tentativas=tentativas,
    )


def _vereditos(pares):
    """Constrói vereditos a partir de (campo, valor, sustentada)."""
    return [
        VerificacaoAfirmacao(campo=c, valor=v, sustentada=s, fonte=("https://f" if s else None))
        for c, v, s in pares
    ]


def _mock_verificar(monkeypatch, pares):
    monkeypatch.setattr(ev, "verificar_afirmacoes", lambda dados, conteudo: _vereditos(pares))


def test_suficiente_com_3_dominios_e_campos(monkeypatch):
    _mock_verificar(monkeypatch, [("setor", "Indústria", True), ("descricao", "faz X", True)])
    out = ev.evidence_validator(_state(["https://a.com/x", "https://b.com/y", "https://c.com/z"]))
    assert out["evidencias_ok"] is True
    assert out["tentativas"] == 1  # incrementou


def test_insuficiente_com_2_dominios(monkeypatch):
    _mock_verificar(monkeypatch, [("setor", "Indústria", True), ("descricao", "faz X", True)])
    out = ev.evidence_validator(_state(["https://a.com/x", "https://b.com/y"]))
    assert out["evidencias_ok"] is False  # pré-gate exige 3 domínios distintos


def test_insuficiente_sem_campos(monkeypatch):
    _mock_verificar(monkeypatch, [])
    out = ev.evidence_validator(
        _state(["https://a.com/x", "https://b.com/y"], descricao="")
    )
    assert out["evidencias_ok"] is False


def test_funding_sem_lastro_e_removido(monkeypatch):
    _mock_verificar(
        monkeypatch,
        [
            ("setor", "Indústria", True),
            ("descricao", "faz X", True),
            ("funding", "Series A $10M", False),  # nenhuma fonte confirma
        ],
    )
    out = ev.evidence_validator(
        _state(
            ["https://a.com/x", "https://b.com/y", "https://c.com/z"],
            funding="Series A $10M",
        )
    )
    # afirmação de alto risco sem lastro foi removida dos dados...
    assert out["dados_estruturados"].funding is None
    # ...mas o veredito ficou registrado (rastreabilidade)
    vfunding = [v for v in out["afirmacoes_verificadas"] if v.campo == "funding"]
    assert vfunding and vfunding[0].sustentada is False
    # setor/descricao sustentados → passa o gate
    assert out["evidencias_ok"] is True


def test_setor_nao_sustentado_dispara_loop(monkeypatch):
    _mock_verificar(
        monkeypatch,
        [("setor", "Indústria", False), ("descricao", "faz X", True)],
    )
    out = ev.evidence_validator(
        _state(["https://a.com/x", "https://b.com/y", "https://c.com/z"])
    )
    assert out["evidencias_ok"] is False  # campo-chave não ancorado → loop


def test_grounding_desabilitado_nao_chama_llm(monkeypatch):
    monkeypatch.setattr(ev.settings, "grounding_habilitado", False)

    def nao_deveria(dados, conteudo):
        raise AssertionError("não deveria chamar o LLM com grounding desabilitado")

    monkeypatch.setattr(ev, "verificar_afirmacoes", nao_deveria)
    out = ev.evidence_validator(_state(["https://a.com/x", "https://b.com/y", "https://c.com/z"]))
    assert out["evidencias_ok"] is True   # cai para a regra mecânica (3 domínios + campos)
    assert out["tentativas"] == 1
