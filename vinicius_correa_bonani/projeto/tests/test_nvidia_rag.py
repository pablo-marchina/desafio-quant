"""Testes do nó nvidia_rag (offline — recuperação monkeypatchada)."""

from app import nvidia_rag, rag
from app.nvidia_rag import _montar_query
from app.state import DadosEmpresa, RadarState


def test_contexto_rag_com_citacoes(monkeypatch):
    monkeypatch.setattr(rag, "recuperar", lambda q: [
        {"texto": "Triton serve modelos eficientemente", "fonte": "https://docs.nvidia.com/triton"},
        {"texto": "TensorRT-LLM otimiza inferência", "fonte": "https://github.com/NVIDIA/TensorRT-LLM"},
    ])
    state = RadarState(dados_estruturados=DadosEmpresa(nome="Tractian", setor="Indústria", tecnologias=["IoT"]))
    out = nvidia_rag.nvidia_rag(state)

    assert len(out["contexto_rag"]) == 2
    assert "[fonte: https://docs.nvidia.com/triton]" in out["contexto_rag"][0]


def test_montar_query_usa_perfil():
    q = _montar_query(RadarState(dados_estruturados=DadosEmpresa(nome="X", setor="Saúde", tecnologias=["LLM"])))
    assert "Saúde" in q and "LLM" in q
