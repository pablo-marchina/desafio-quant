from __future__ import annotations

import json
import os
import threading
from typing import Any
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request


BASE_URL = os.getenv("NVIDIA_RADAR_API_URL", "http://127.0.0.1:8000").rstrip("/")
FIXTURE_PORT = int(os.getenv("NVIDIA_RADAR_SMOKE_FIXTURE_PORT", "8765"))


class StartupFixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        pages = {
            "/": """
                <html><body>
                <main>
                  <h1>RouteOps AI</h1>
                  <p>Startup brasileira de logistics AI com operacao no Brasil,
                  modelos proprietarios para otimizar rotas, scheduling e
                  operacoes em tempo real.</p>
                  <a href="/product">Product</a>
                  <a href="/docs">Docs</a>
                </main>
                </body></html>
            """,
            "/product": """
                <html><body><main>
                  <h1>Inference platform</h1>
                  <p>O produto usa machine learning, inference em producao,
                  baixa latencia e pipelines de dados para simular cenarios
                  de entrega, roteirizacao e capacidade operacional.</p>
                </main></body></html>
            """,
            "/docs": """
                <html><body><main>
                  <h1>Technical notes</h1>
                  <p>Arquitetura com dados proprietarios, otimizacao de rotas,
                  scheduling, analytics, APIs internas e monitoramento de modelos.</p>
                </main></body></html>
            """,
        }
        body = pages.get(self.path, pages["/"]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def start_fixture_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", FIXTURE_PORT), StartupFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def post_json(path: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
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


def assert_any(products: list[str], expected: set[str], label: str, top_n: int = 3) -> None:
    candidates = set(products[:top_n])
    if not candidates & expected:
        raise AssertionError(
            f"{label}: esperado um de {sorted(expected)} no top {top_n}, veio {products}"
        )


def run_search(label: str, query: str, expected: set[str]) -> None:
    response = post_json("/rag/search", {"query": query, "limit": 5})
    products = [result["product_name"] for result in response["results"]]
    sources = [result.get("metadata", {}).get("source_type") for result in response["results"]]
    assert_any(products, expected, label)
    print(f"[ok] {label}: {products}")
    print(f"     fontes: {sources}")


def run_smoke_checks() -> int:
    health = get_json("/health")
    if health.get("status") != "ok":
        qdrant = health.get("qdrant", {})
        postgres = health.get("postgres", {})
        raise AssertionError(
            "Health nao esta ok. "
            f"status={health.get('status')} "
            f"qdrant={qdrant.get('status')} "
            f"postgres={postgres.get('status')}. "
            "Para o smoke completo, suba Qdrant/Postgres com "
            "`docker compose up -d qdrant postgres`, ingira a base NVIDIA e tente novamente."
        )

    embedding = health.get("embedding", {})
    postgres = health.get("postgres", {})
    print(
        "[ok] health: "
        f"provider={embedding.get('provider')} "
        f"model={embedding.get('model')} "
        f"size={embedding.get('vector_size')} "
        f"postgres={postgres.get('status')}"
    )

    run_search(
        "LLM/inferencia",
        "startup usa LLM em atendimento com problema de latencia e custo de inferencia",
        {"NVIDIA NIM", "TensorRT-LLM", "NVIDIA Triton Inference Server", "NVIDIA NeMo"},
    )
    run_search(
        "dados tabulares",
        "startup processa dados tabulares pandas machine learning",
        {"NVIDIA RAPIDS", "cuDF", "cuML"},
    )
    run_search(
        "cybersecurity",
        "cybersecurity threat detection anomaly telemetry fraud real time",
        {"NVIDIA Morpheus"},
    )
    run_search(
        "agents/blueprints",
        "startup precisa construir AI agents com blueprints e workflows RAG",
        {"NVIDIA AI Blueprints", "NVIDIA NeMo", "NVIDIA NIM"},
    )
    run_search(
        "otimizacao/logistica",
        "startup precisa otimizar rotas logistica scheduling operacoes",
        {"NVIDIA cuOpt"},
    )
    run_search(
        "ambiente/containers",
        "startup quer ambiente reprodutivel containers modelos GPU",
        {"NVIDIA AI Workbench", "NVIDIA NGC"},
    )

    radar = post_json(
        "/startup/radar",
        {"sector": "logistics", "focus": "rotas scheduling optimization", "limit": 5},
    )
    if not radar.get("results"):
        raise AssertionError(f"Radar vazio: {radar}")
    if radar["results"][0]["opportunity_percent"] <= 0:
        raise AssertionError(f"Radar sem porcentagem valida: {radar}")
    print(
        "[ok] startup_radar: "
        f"{[(item['startup_name'], item['opportunity_percent']) for item in radar['results']]}"
    )

    analysis = post_json(
        "/analysis/startup",
        {
            "startup_name": "Smoke Health AI",
            "sector": "healthcare",
            "description": (
                "Startup usa IA generativa, LLM, dados clinicos, workflow e pipeline "
                "em producao."
            ),
            "technical_gaps": ["latencia de inferencia", "governanca de IA"],
        },
    )
    recommendations = [item["technology"] for item in analysis["recommendations"]]
    if not analysis.get("briefing_markdown") or not recommendations:
        raise AssertionError(f"Analise incompleta: {analysis}")
    if analysis.get("search_plan", {}).get("version") != "search_plan_v1":
        raise AssertionError(f"Plano de busca ausente ou invalido: {analysis}")
    if not analysis.get("structured_profile", {}).get("ai_signals"):
        raise AssertionError(f"Perfil estruturado sem sinais de IA: {analysis}")
    for recommendation in analysis["recommendations"]:
        if not recommendation.get("implementation_complexity"):
            raise AssertionError(f"Recomendacao sem complexidade: {recommendation}")
        if not recommendation.get("next_action"):
            raise AssertionError(f"Recomendacao sem proxima acao: {recommendation}")
    if "Plano de busca" not in analysis["briefing_markdown"]:
        raise AssertionError("Briefing sem secao de plano de busca.")
    if postgres.get("enabled") and postgres.get("status") == "ok":
        if not analysis.get("analysis_run_id"):
            raise AssertionError(f"Analise nao foi salva no Postgres: {analysis}")
        history = get_json("/analysis/runs?limit=5")
        if not history:
            raise AssertionError("Historico Postgres vazio apos analise.")

    print(
        "[ok] analysis: "
        f"classification={analysis['classification']} "
        f"ai={analysis['ai_native_score']} "
        f"fit={analysis['nvidia_fit_score']} "
        f"run_id={analysis.get('analysis_run_id')} "
        f"plan={analysis['search_plan']['version']} "
        f"recommendations={recommendations}"
    )

    evidence_analysis = post_json(
        "/analysis/startup",
        {
            "startup_name": "RouteOps AI Fixture",
            "website_url": f"http://127.0.0.1:{FIXTURE_PORT}/",
            "sector": "logistics",
            "description": "Startup usa IA para rotas, scheduling e operacoes.",
            "technical_gaps": ["otimizacao de rotas", "latencia de inferencia"],
        },
    )
    if evidence_analysis.get("startup_evidence_chunks", 0) <= 0:
        raise AssertionError(f"Evidencias da startup nao foram ingeridas: {evidence_analysis}")
    if not evidence_analysis.get("analysis_run_id"):
        raise AssertionError(
            "Analise com evidencia nao recebeu analysis_run_id; "
            "confira se Postgres esta ativo para o smoke completo."
        )

    evidence = post_json(
        "/startup/evidence/search",
        {
            "query": "rotas scheduling baixa latencia inference",
            "analysis_run_id": evidence_analysis["analysis_run_id"],
            "limit": 5,
        },
    )
    if not evidence.get("results"):
        raise AssertionError(f"Busca de evidencia vazia: {evidence}")

    print(
        "[ok] startup_evidence: "
        f"chunks={evidence_analysis['startup_evidence_chunks']} "
        f"results={[item['source_url'] for item in evidence['results']]}"
    )
    return 0


def main() -> int:
    fixture_server = start_fixture_server()
    try:
        return run_smoke_checks()
    except (AssertionError, RuntimeError) as error:
        print(f"[fail] smoke: {error}")
        print(
            "Dica: verifique `GET /health`, Docker Desktop, Qdrant em localhost:6333 "
            "e Postgres antes de rodar `--with-smoke`."
        )
        return 1
    finally:
        fixture_server.shutdown()
        fixture_server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
