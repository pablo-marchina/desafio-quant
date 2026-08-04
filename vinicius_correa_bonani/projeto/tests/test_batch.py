"""Teste do runner em lote (offline — grafo e persistência monkeypatchados)."""

from app import batch


def test_analisar_roda_grafo_e_persiste(monkeypatch):
    fake_final = {"alvos": ["X"], "classificacao": "ai-native"}
    monkeypatch.setattr(batch.graph, "invoke", lambda state: fake_final)

    salvos = []
    monkeypatch.setattr(batch.db, "salvar_resultado", lambda final: salvos.append(final))

    out = batch.analisar("X")

    assert out is fake_final
    assert salvos == [fake_final]   # persistiu uma vez


def test_lote_continua_apos_erro(monkeypatch):
    def invoke(state):
        if state.consulta == "ruim":
            raise RuntimeError("falhou")
        return {"alvos": [state.consulta]}

    monkeypatch.setattr(batch.graph, "invoke", invoke)
    monkeypatch.setattr(batch.db, "salvar_resultado", lambda final: None)

    res = batch.analisar_lote(["boa", "ruim", "boa2"])
    assert len(res) == 2   # a que falhou não derruba o lote
