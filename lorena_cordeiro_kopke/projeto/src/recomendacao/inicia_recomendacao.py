from __future__ import annotations

"""
Orquestrador do pipeline de recomendação de tecnologias NVIDIA.

Executa um grafo LangGraph com 4 agentes LLM sequenciais para cada empresa elegível:
  carregar_perfil → montar_query → buscar_e_reranquear
  → explicar_tecnico / explicar_negocio → validar_json
  → sintese_executiva → roadmap_adocao → kit_inicio → salvar_resultado

Execute com:
  python src/recomendacao/inicia_recomendacao.py
  python src/recomendacao/inicia_recomendacao.py --empresa-id 42
  python src/recomendacao/inicia_recomendacao.py --forcar
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_RAIZ / "src"))

from dotenv import load_dotenv
load_dotenv(_RAIZ / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_PAUSA_ENTRE_EMPRESAS = 2.0


def _separador(titulo: str) -> None:
    print()
    print("=" * 60)
    print(f"  {titulo}")
    print("=" * 60)


def _ja_tem_resultado(empresa_id: int) -> bool:
    """Retorna True se a empresa já tem chunks_reranqueados salvos (recomendação já gerada)."""
    from supabase import create_client
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    resultado = (
        supabase.table("recomendacoes_nvidia")
        .select("chunks_reranqueados")
        .eq("empresa_id", empresa_id)
        .not_.is_("chunks_reranqueados", "null")
        .limit(1)
        .execute()
        .data
    )
    if not resultado:
        return False
    chunks = resultado[0].get("chunks_reranqueados")
    return bool(chunks)


def _rodar_grafo(empresa_id: int) -> dict | None:
    """Instancia e executa o grafo LangGraph para uma empresa. Retorna output_final."""
    from agents.extras.graph import criar_grafo

    grafo = criar_grafo()
    try:
        resultado = grafo.invoke(
            {"empresa_id": empresa_id},
            config={"configurable": {"thread_id": f"empresa-{empresa_id}"}},
        )
        return resultado.get("output_final")
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] erro inesperado no grafo: %s", empresa_id, exc)
        return None


def rodar(
    empresa_id: int | None = None,
    forcar: bool = False,
) -> None:
    """
    Executa o pipeline completo de recomendação via LangGraph.

    Args:
        empresa_id: processa só essa empresa se informado; senão processa todas elegíveis.
        forcar:     reprocessa mesmo que recomendações já existam no banco.
    """
    from recomendacao.verifica_situacao_coleta import verificar

    ids_elegiveis = verificar(empresa_id=empresa_id)

    if not ids_elegiveis:
        logger.warning("Nenhuma empresa elegível — pipeline encerrado.")
        return

    logger.info(
        "Iniciando pipeline LangGraph | %d empresa(s) | forcar=%s",
        len(ids_elegiveis), forcar,
    )

    processadas = erros = puladas = 0

    for eid in ids_elegiveis:
        if not forcar and _ja_tem_resultado(eid):
            logger.info("[%s] já tem resultado — pulando (use --forcar para reprocessar)", eid)
            puladas += 1
            continue

        _separador(f"Empresa {eid}")
        output = _rodar_grafo(eid)

        if output is None:
            logger.error("[%s] grafo encerrou sem output_final", eid)
            erros += 1
        elif "erro" in output:
            logger.warning("[%s] sem_resultado: %s", eid, output["erro"])
            erros += 1
        else:
            tecnologias = [
                t.get("tecnologia")
                for t in output.get("explicacao", {}).get("tecnologias", [])
            ]
            print(f"  [{eid}] OK — {tecnologias}")
            processadas += 1

        if eid != ids_elegiveis[-1]:
            time.sleep(_PAUSA_ENTRE_EMPRESAS)

    _separador("Pipeline concluído")
    print(f"  processadas: {processadas} | puladas: {puladas} | erros: {erros}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline de recomendação NVIDIA via LangGraph.",
    )
    parser.add_argument(
        "--empresa-id",
        type=int,
        default=None,
        help="Processa só essa empresa.",
    )
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Reprocessa mesmo que recomendações já existam no banco.",
    )
    args = parser.parse_args()

    rodar(
        empresa_id=args.empresa_id,
        forcar=args.forcar,
    )
