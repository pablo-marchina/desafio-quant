from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib import error, request

from rag_eval_cases import RAG_EVAL_CASES


BASE_URL = os.getenv("NVIDIA_RADAR_API_URL", "http://127.0.0.1:8000").rstrip("/")


def post_json(path: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {path} retornou HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"POST {path} falhou ao conectar em {BASE_URL}: {exc.reason}"
        ) from exc


def get_json(path: str, timeout: int = 20) -> dict[str, Any]:
    try:
        with request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {path} retornou HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"GET {path} falhou ao conectar em {BASE_URL}: {exc.reason}"
        ) from exc


def assert_rag_ready() -> None:
    health = get_json("/health")
    if health.get("status") != "ok":
        qdrant = health.get("qdrant", {})
        postgres = health.get("postgres", {})
        raise RuntimeError(
            "API nao esta pronta para avaliacao RAG. "
            f"status={health.get('status')} "
            f"qdrant={qdrant.get('status')} "
            f"postgres={postgres.get('status')}. "
            "Suba Qdrant, ingira a base NVIDIA e confira `/health` antes de rodar."
        )


def evaluate_case(case: dict[str, object], *, limit: int, top_n: int) -> dict[str, object]:
    response = post_json(
        "/rag/search",
        {"query": str(case["query"]), "limit": limit},
    )
    results = response.get("results") or []
    products = [str(result.get("product_name") or "") for result in results]
    expected = set(str(product) for product in case["expected_products"])
    matched = sorted(set(products[:top_n]) & expected)
    missing_sources = [
        product
        for product, result in zip(products, results, strict=False)
        if not str(result.get("source_url") or "").startswith(("http://", "https://"))
    ]
    rerank_providers = [
        str((result.get("metadata") or {}).get("rerank", {}).get("provider") or "")
        for result in results
    ]
    return {
        "id": case["id"],
        "query": case["query"],
        "expected_products": sorted(expected),
        "top_products": products[:top_n],
        "matched_expected": matched,
        "passed": bool(matched) and not missing_sources,
        "missing_sources": missing_sources,
        "rerank_providers": rerank_providers[:top_n],
    }


def run_evaluation(*, limit: int = 5, top_n: int = 5) -> dict[str, object]:
    assert_rag_ready()
    results = [evaluate_case(case, limit=limit, top_n=top_n) for case in RAG_EVAL_CASES]
    passed = sum(1 for result in results if result["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / max(1, len(results)) * 100, 1),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Avalia o RAG NVIDIA com 15 perguntas fixas do TAPI."
    )
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio em JSON.")
    parser.add_argument("--limit", type=int, default=5, help="Quantidade de resultados por busca.")
    parser.add_argument("--top-n", type=int, default=5, help="Top N considerado para match.")
    args = parser.parse_args()

    try:
        report = run_evaluation(limit=args.limit, top_n=args.top_n)
    except RuntimeError as error:
        print(f"[fail] RAG eval: {error}")
        print(
            "Dica: rode a API, suba Qdrant, ingira a base NVIDIA e confira `/health` "
            "antes de executar a avaliacao."
        )
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "RAG eval: "
            f"{report['passed']}/{report['total']} passaram "
            f"({report['pass_rate']}%)."
        )
        for result in report["results"]:
            marker = "ok" if result["passed"] else "fail"
            print(
                f"[{marker}] {result['id']}: "
                f"top={result['top_products']} "
                f"match={result['matched_expected']}"
            )

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
