from __future__ import annotations

import argparse
import os
import json
from pprint import pprint
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _sample_documents(startup_name: str) -> list[dict]:
    return [
        {
            "url": "https://acme.ai",
            "titulo": f"{startup_name} | Official Website",
            "fonte_tipo": "site_oficial",
            "texto": (
                f"{startup_name} is a Brazilian startup building voice agents and LLM workflows "
                "for hospitals and clinics. The platform automates patient intake and backoffice tasks."
            ),
            "coletado_em": "2026-06-29T00:00:00+00:00",
            "metodo_coleta": "debug_script",
            "status_http": 200,
        },
        {
            "url": "https://www.cubo.itau.com.br/startups/acme-ai",
            "titulo": f"{startup_name} na vitrine Cubo",
            "fonte_tipo": "directory_profile",
            "texto": (
                f"{startup_name} develops generative AI copilots for healthcare operations. "
                "Business model: B2B SaaS."
            ),
            "coletado_em": "2026-06-29T00:00:00+00:00",
            "metodo_coleta": "debug_script",
            "status_http": 200,
        },
        {
            "url": "https://www.linkedin.com/company/acme-ai",
            "titulo": f"{startup_name} | LinkedIn",
            "fonte_tipo": "linkedin",
            "texto": f"{startup_name} helps clinics with AI automation.",
            "coletado_em": "2026-06-29T00:00:00+00:00",
            "metodo_coleta": "debug_script",
            "status_http": 200,
        },
    ]


def _print_section(title: str, payload) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
        return
    pprint(payload, sort_dicts=False)


def _build_llm_diagnostics(state: dict) -> dict:
    startup = state.get("structured_startup")
    startup_metadata = startup.metadata if startup else {}
    rag_quality = (state.get("quality_flags") or {}).get("rag") or {}
    rag_context = state.get("rag_context")
    rag_items = rag_context.items if rag_context else []
    rag_metadata = rag_context.metadata if rag_context else {}

    return {
        "extraction_provider": startup_metadata.get("extraction_provider"),
        "extraction_status": startup_metadata.get("extraction_status"),
        "llm_extraction_present": bool(startup_metadata.get("llm_extraction")),
        "validator_status": (state.get("validation_report") or {}).get("status"),
        "rag_used_fallback": rag_quality.get("used_fallback"),
        "rag_item_count": len(rag_items),
        "rag_rerank_provider": rag_metadata.get("rerank_provider"),
        "rag_rerank_status": rag_metadata.get("rerank_status"),
        "rag_rerank_reasons": rag_metadata.get("rerank_reasons"),
        "rag_rerank_scores": [item.rerank_score for item in rag_items[:5]],
        "rag_citations": [item.citation for item in rag_items[:5]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa o pipeline LangGraph com dados de exemplo e imprime o estado final."
    )
    parser.add_argument(
        "--startup",
        default="Acme AI",
        help="Nome da startup usada no teste manual.",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Query opcional. Se omitida, usa o nome da startup.",
    )
    parser.add_argument(
        "--documents-json",
        default=None,
        help="Caminho opcional para um JSON com raw_documents customizados.",
    )
    parser.add_argument(
        "--heuristic-only",
        action="store_true",
        help="Desabilita a extracao via LLM nesta execucao para debug local rapido.",
    )
    args = parser.parse_args()

    if args.heuristic_only:
        os.environ["EXTRACTION_PROVIDER"] = "heuristic"

    if args.documents_json:
        with open(args.documents_json, "r", encoding="utf-8") as fp:
            documents = json.load(fp)
    else:
        documents = _sample_documents(args.startup)

    from src.agents import build_startup_pipeline

    graph = build_startup_pipeline()
    state = graph.invoke(
        {
            "query": args.query or args.startup,
            "target_startup": args.startup,
            "raw_documents": documents,
        }
    )

    _print_section("Logs", state.get("logs"))
    _print_section("Quality Flags", state.get("quality_flags"))
    _print_section("LLM Diagnostics", _build_llm_diagnostics(state))
    _print_section("Validation Report", state.get("validation_report"))
    _print_section("Structured Startup", state.get("structured_startup").model_dump() if state.get("structured_startup") else None)
    _print_section(
        "Validated Evidences",
        [item.model_dump() for item in state.get("validated_evidences", [])],
    )
    _print_section("Final Briefing", state.get("final_briefing"))


if __name__ == "__main__":
    main()
