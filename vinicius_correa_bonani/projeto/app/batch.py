"""Runner — roda o grafo por empresa (sequencial) e persiste o resultado.

Ponto único de execução, usado por CLI, lote e Streamlit:

    python -m app.batch "Tractian" "Gupy" "iFood"

Sequencial: respeita o rate-limit dos tiers free (Groq, Gemini, Cohere).
"""

import sys

from app import db
from app.graph import graph
from app.state import RadarState


def analisar(consulta: str) -> dict:
    """Roda o pipeline completo para uma empresa e persiste o resultado."""
    final = graph.invoke(RadarState(consulta=consulta))
    db.salvar_resultado(final)
    return final


def analisar_stream(consulta: str):
    """Como `analisar`, mas GERADOR: emite eventos conforme o grafo anda.

    Usa graph.stream com dois modos combinados (chunks viram tuplas
    (modo, chunk)): "updates" diz QUAL NÓ acabou de rodar (o progresso);
    "values" traz o estado acumulado, e o último é o final completo, que
    persistimos como no invoke. Aguenta o loop (nó repetido re-emite) e o
    desvio non-ai (o fluxo só termina mais cedo).

    Eventos yieldados: {"agente": <nome_do_nó>} a cada nó e, por fim,
    {"done": True, "classificacao": ...}.
    """
    final: dict | None = None
    for modo, chunk in graph.stream(
        RadarState(consulta=consulta), stream_mode=["updates", "values"]
    ):
        if modo == "updates":
            for nome_no in chunk:
                yield {"agente": nome_no}
        else:  # "values": estado acumulado até aqui; o último é o final
            final = chunk
    if final is not None:
        db.salvar_resultado(final)
    yield {"done": True, "classificacao": (final or {}).get("classificacao")}


def analisar_lote(consultas: list[str]) -> list[dict]:
    resultados: list[dict] = []
    for i, consulta in enumerate(consultas, 1):
        print(f"[{i}/{len(consultas)}] analisando: {consulta}")
        try:
            final = analisar(consulta)
            sc = final.get("score")
            print(f"   -> {final.get('classificacao')} | score {sc.composto if sc else '—'}")
            resultados.append(final)
        except Exception as e:  # uma empresa que falha não derruba o lote
            print(f"   ! erro: {type(e).__name__}: {e}")
    return resultados


def main() -> None:
    consultas = sys.argv[1:] or ["Tractian"]
    analisar_lote(consultas)


if __name__ == "__main__":
    main()
