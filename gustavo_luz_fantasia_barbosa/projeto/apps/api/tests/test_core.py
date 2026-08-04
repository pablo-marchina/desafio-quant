from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.briefing import generate_briefing_markdown, validate_evidence
from app.briefing_export import build_pdf
from app.main import (
    build_candidate_profile,
    build_local_tool_fits,
    candidate_matches,
    score_startup_profile,
)
from app.pipeline import PipelineTrace, SequentialStateGraph
from app.profile_extraction import extract_structured_profile
from app.rag.embeddings import HashEmbeddingProvider
from app.rag.freshness import (
    check_nvidia_source,
    classify_startup_usefulness,
    content_hash,
)
from app.rag.reranker import bm25_scores, rerank_results
from app.schemas.analysis import (
    StartupRecommendation,
    StartupSearchPlan,
    StartupSourceSummary,
)
from app.scraping import (
    extract_candidate_links,
    has_brazilian_startup_signal,
    normalize_text,
)
from app.startup_sources import (
    load_startup_candidates,
    resolve_startup_by_name,
    search_startup_candidates,
)
import app.startup_discovery as startup_discovery_module
from app.startup_discovery import (
    ACEDiscoveryAdapter,
    BrazilJournalDiscoveryAdapter,
    EndeavorDiscoveryAdapter,
    ExameDiscoveryAdapter,
    GenericNewsDiscoveryAdapter,
    PEGNDiscoveryAdapter,
    StartSeDiscoveryAdapter,
    StartupiDiscoveryAdapter,
    StartupsComBrDiscoveryAdapter,
    ValorDiscoveryAdapter,
    choose_official_website,
    collect_discoveries_from_sources,
    discovery_adapter_for_url,
    extract_startup_name,
    parse_discovery_source_urls,
    startup_name_key,
    use_discovered_startups,
    write_discoveries,
)
from app.startups.source_metadata import (
    build_startup_source_evidence,
    startup_source_confidence,
)
from app.storage import startup_key
from scripts.check_startup_sources import (
    configured_source_urls,
    evaluate_source_quality,
    summarize_source_result,
)
from scripts.rag_eval_cases import RAG_EVAL_CASES, required_technology_coverage


class EmbeddingTests(unittest.TestCase):
    def test_hash_embedding_is_deterministic_and_normalized(self) -> None:
        provider = HashEmbeddingProvider(vector_size=64)

        first = provider.embed("IA generativa com baixa latencia")
        second = provider.embed("IA generativa com baixa latencia")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertGreater(sum(abs(value) for value in first), 0)


class RagEvaluationCaseTests(unittest.TestCase):
    def test_rag_eval_has_required_15_questions_and_core_coverage(self) -> None:
        self.assertGreaterEqual(len(RAG_EVAL_CASES), 15)
        covered_products = set()
        for case in RAG_EVAL_CASES:
            covered_products.update(case["expected_products"])

        self.assertTrue(required_technology_coverage().issubset(covered_products))


class PipelineGraphTests(unittest.TestCase):
    def test_state_graph_records_skips_and_retries(self) -> None:
        class State:
            def __init__(self) -> None:
                self.current_step = None
                self.calls = 0
                self.did_work = False

        state = State()
        trace = PipelineTrace()
        graph = SequentialStateGraph(trace)

        def flaky_node(inner_state: State) -> None:
            inner_state.calls += 1
            if inner_state.calls == 1:
                raise TimeoutError("temporary")
            inner_state.did_work = True
            inner_state.current_step.finish(summary="Recovered.")

        graph.add_node(
            "freshness",
            "Knowledge Freshness Agent",
            lambda inner_state: None,
            condition=lambda inner_state: False,
        )
        graph.add_node(
            "rag",
            "NVIDIA RAG Agent",
            flaky_node,
            retries=1,
            retry_exceptions=(TimeoutError,),
        )

        graph.run(state)
        steps = trace.as_list()

        self.assertEqual(steps[0]["status"], "skipped")
        self.assertEqual(steps[1]["status"], "retrying")
        self.assertEqual(steps[2]["status"], "completed")
        self.assertEqual(steps[2]["metadata"]["attempt"], 2)
        self.assertTrue(state.did_work)


class NvidiaFreshnessTests(unittest.TestCase):
    def test_content_hash_is_stable_for_whitespace_changes(self) -> None:
        self.assertEqual(content_hash("NVIDIA  NIM\ninference"), content_hash("NVIDIA NIM inference"))

    def test_usefulness_classifier_detects_startup_relevant_topics(self) -> None:
        result = classify_startup_usefulness(
            "NVIDIA NIM deployment improves inference latency and production serving."
        )

        self.assertTrue(result["is_useful_for_startups"])
        self.assertIn("model_deployment", result["useful_topics"])
        self.assertGreater(result["usefulness_score"], 20)

    def test_source_check_compares_hash_against_local_snapshot(self) -> None:
        def fake_fetcher(_url: str, _max_chars: int) -> dict[str, object]:
            return {
                "source_url": "https://example.test/nim",
                "status_code": 200,
                "headers": {"Last-Modified": "Fri, 26 Jun 2026 12:00:00 GMT"},
                "html": "",
                "text": "NVIDIA NIM deployment inference latency production serving.",
                "characters": 64,
            }

        check = check_nvidia_source(
            {
                "product_name": "NVIDIA NIM",
                "category": "model_deployment",
                "source_url": "https://example.test/nim",
                "summary": "Optimized inference microservices.",
            },
            local_snapshot={"content_hash": "old", "modified_at": "2026-06-01T00:00:00+00:00"},
            fetcher=fake_fetcher,
        )

        self.assertEqual(check["status"], "outdated")
        self.assertEqual(check["action"], "ingest_candidate")
        self.assertTrue(check["is_useful_for_startups"])


class StartupScoringTests(unittest.TestCase):
    def test_scores_ai_native_profile_above_wrapper_profile(self) -> None:
        ai_native = (
            "Startup brasileira usa IA, LLM, dados proprietarios, workflow, "
            "pipeline, inferencia em producao, latencia e governanca."
        )
        wrapper = "Chatbot com interface simples em cima de API externa da OpenAI."

        ai_classification, ai_score, ai_wrapper_risk, _fit = score_startup_profile(
            ai_native,
            recommendation_count=4,
        )
        wrapper_classification, _wrapper_score, wrapper_risk, _fit = (
            score_startup_profile(wrapper, recommendation_count=1)
        )

        self.assertEqual(ai_classification, "ai_native")
        self.assertEqual(wrapper_classification, "wrapper_risk")
        self.assertGreater(ai_score, 70)
        self.assertLess(ai_wrapper_risk, wrapper_risk)

    def test_classifies_non_ai_separately_from_insufficient_evidence(self) -> None:
        non_ai = (
            "Startup brasileira de marketplace B2B para compras corporativas, "
            "gestao de fornecedores, pagamentos e operacao logistica nacional."
        )
        sparse = "Empresa brasileira."

        non_ai_classification, non_ai_score, _risk, _fit = score_startup_profile(
            non_ai,
            recommendation_count=0,
        )
        sparse_classification, _score, _risk, _fit = score_startup_profile(
            sparse,
            recommendation_count=0,
        )

        self.assertEqual(non_ai_classification, "non_ai")
        self.assertLess(non_ai_score, 45)
        self.assertEqual(sparse_classification, "insufficient_evidence")

    def test_candidate_matching_and_tool_fit_for_logistics(self) -> None:
        candidate = {
            "startup_name": "RouteOps Brasil",
            "sector": "logistics",
            "description": "Startup brasileira de IA para rotas e scheduling.",
            "signals": ["rotas", "optimization", "machine learning"],
        }

        profile = build_candidate_profile(candidate, "rotas scheduling")
        tools = build_local_tool_fits(profile)

        self.assertTrue(candidate_matches(candidate, "logistics", "rotas"))
        self.assertEqual(tools[0].technology, "NVIDIA cuOpt")
        self.assertGreaterEqual(tools[0].fit_percent, 35)

    def test_hybrid_reranker_promotes_domain_fit_over_raw_vector_score(self) -> None:
        results = [
            {
                "score": 0.9,
                "payload": {
                    "product_name": "NVIDIA RAPIDS",
                    "category": "data_processing",
                    "source_type": "seed",
                    "summary": "GPU dataframes and analytics.",
                    "chunk_text": "Acelera pipelines tabulares e analytics.",
                },
            },
            {
                "score": 0.62,
                "payload": {
                    "product_name": "NVIDIA cuOpt",
                    "category": "optimization",
                    "source_type": "official_page",
                    "summary": "Optimization for routing, logistics and scheduling.",
                    "chunk_text": "Resolve rotas, scheduling, planejamento logistico e otimizacao.",
                },
            },
        ]

        reranked = rerank_results(
            results,
            "startup brasileira de logistica precisa otimizar rotas e scheduling",
        )

        self.assertEqual(reranked[0]["payload"]["product_name"], "NVIDIA cuOpt")
        self.assertIn("rerank_details", reranked[0])
        self.assertEqual(reranked[0]["rerank_details"]["provider"], "hybrid")
        self.assertIn("bm25_score", reranked[0]["rerank_details"])

    def test_bm25_scores_rank_lexically_relevant_document(self) -> None:
        scores = bm25_scores(
            "latencia inferencia llm",
            [
                "RAPIDS acelera dataframes e analytics em GPU.",
                "NIM e Triton reduzem latencia de inferencia para LLM em producao.",
            ],
        )

        self.assertGreater(scores[1], scores[0])


class StartupSourceTests(unittest.TestCase):
    def test_loads_configured_csv_source_and_resolves_name(self) -> None:
        candidates = load_startup_candidates("data/startups_br.csv")
        names = {str(candidate["startup_name"]) for candidate in candidates}

        self.assertIn("Loggi", names)
        self.assertGreaterEqual(len(candidates), 10)

        resolved = resolve_startup_by_name(candidates, "loggi")

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["startup_name"], "Loggi")
        self.assertEqual(resolved["sector"], "logistics")
        self.assertEqual(resolved["source"], "curated_csv")

    def test_search_startup_candidates_scores_partial_queries(self) -> None:
        candidates = load_startup_candidates("data/startups_br.csv")
        results = search_startup_candidates(candidates, "bot city automation", limit=3)

        self.assertTrue(results)
        self.assertEqual(results[0]["startup_name"], "BotCity")
        self.assertGreater(int(results[0]["match_score"]), 0)


class StartupDiscoveryTests(unittest.TestCase):
    def test_extracts_startup_name_from_news_title(self) -> None:
        self.assertEqual(
            extract_startup_name(
                "Vixtra levanta R$ 50 milhões em Série A para expandir infraestrutura financeira"
            ),
            "Vixtra",
        )
        self.assertIsNone(
            extract_startup_name(
                "Oracle lança programa para apoiar startups na América Latina"
            )
        )
        self.assertIsNone(
            extract_startup_name(
                "O código do alto desempenho: a lição da Copa do Mundo para startups"
            )
        )
        self.assertIsNone(extract_startup_name("Por Startupi"))
        self.assertEqual(
            extract_startup_name("M&A Zucchetti compra Omnibees para criar gigante tech"),
            "Zucchetti",
        )
        self.assertIsNone(
            extract_startup_name("M&A Com compra da Whalar, Accenture acelera passos")
        )

    def test_chooses_official_website_from_article_links(self) -> None:
        website = choose_official_website(
            "Vixtra",
            "https://startupi.com.br/vixtra-levanta-r-50-milhoes/",
            [
                {"title": "LinkedIn", "url": "https://linkedin.com/company/vixtra"},
                {
                    "title": "Vixtra",
                    "url": "https://api.whatsapp.com/send/?text=https://startupi.com.br/vixtra",
                },
                {"title": "Vixtra", "url": "https://vixtra.com.br/"},
                {"title": "Outra noticia", "url": "https://startupi.com.br/outra"},
            ],
        )

        self.assertEqual(website, "https://vixtra.com.br/")

    def test_rejects_share_links_as_official_website(self) -> None:
        website = choose_official_website(
            "Vixtra",
            "https://startupi.com.br/vixtra-levanta-r-50-milhoes/",
            [
                {
                    "title": "Vixtra",
                    "url": "https://api.whatsapp.com/send/?text=https://startupi.com.br/vixtra",
                },
                {"title": "Vixtra no LinkedIn", "url": "https://linkedin.com/company/vixtra"},
            ],
        )

        self.assertIsNone(website)

    def test_discovery_sources_parse_unique_urls(self) -> None:
        urls = parse_discovery_source_urls(
            "https://startupi.com.br/, https://startups.com.br/, https://startupi.com.br/",
            "https://fallback.example",
        )

        self.assertEqual(urls, ["https://startupi.com.br/", "https://startups.com.br/"])

    def test_discovery_adapter_selection_uses_source_domain(self) -> None:
        cases = [
            ("https://startupi.com.br/", StartupiDiscoveryAdapter),
            ("https://startups.com.br/negocios/fintech/", StartupsComBrDiscoveryAdapter),
            ("https://exame.com/negocios/", ExameDiscoveryAdapter),
            ("https://braziljournal.com/", BrazilJournalDiscoveryAdapter),
            ("https://www.startse.com/", StartSeDiscoveryAdapter),
            ("https://endeavor.org.br/", EndeavorDiscoveryAdapter),
            ("https://aceventures.com.br/blog/", ACEDiscoveryAdapter),
            ("https://acestartups.com.br/", ACEDiscoveryAdapter),
            ("https://revistapegn.globo.com/startups/", PEGNDiscoveryAdapter),
            ("https://valor.globo.com/empresas/startups/", ValorDiscoveryAdapter),
        ]
        for source_url, adapter_type in cases:
            self.assertIsInstance(discovery_adapter_for_url(source_url), adapter_type)

        self.assertIsInstance(
            discovery_adapter_for_url("https://example.com/startups"),
            GenericNewsDiscoveryAdapter,
        )

    def test_discovery_adapter_collects_and_deduplicates_links_without_network(self) -> None:
        adapter = StartupiDiscoveryAdapter("https://startupi.com.br/")

        discoveries = adapter.collect_from_links(
            [
                {
                    "title": "Vixtra levanta rodada Serie A para expandir fintech",
                    "url": "https://startupi.com.br/vixtra-levanta-rodada/",
                },
                {
                    "title": "Vixtra levanta nova rodada para expandir fintech",
                    "url": "https://startupi.com.br/vixtra-nova-rodada/",
                },
                {
                    "title": "Oracle lanca programa para apoiar startups",
                    "url": "https://startupi.com.br/oracle-programa/",
                },
                {
                    "title": "RouteOps capta investimento para otimizar rotas",
                    "url": "https://outro.example/routeops/",
                },
            ],
            response_url="https://startupi.com.br/",
            max_items=5,
        )

        self.assertEqual(len(discoveries), 1)
        self.assertEqual(discoveries[0]["startup_name"], "Vixtra")
        self.assertEqual(discoveries[0]["source"], "startupi_news")
        self.assertIn("startupi", discoveries[0]["signals"])

    def test_extract_startup_name_handles_common_news_patterns(self) -> None:
        self.assertEqual(
            extract_startup_name("A Vixtra levanta R$ 50 milhões em Série A"),
            "Vixtra",
        )
        self.assertEqual(
            extract_startup_name("Fintech Credix capta rodada para crescer"),
            "Credix",
        )
        self.assertEqual(
            extract_startup_name("Startup NeuralOps anuncia plataforma de IA"),
            "NeuralOps",
        )

    def test_source_metadata_scores_public_and_official_sources(self) -> None:
        candidate = {
            "startup_name": "Vixtra",
            "source": "enriched_startupi",
            "website_url": "https://vixtra.com.br",
            "github_url": "",
            "source_url": "https://startupi.com.br/vixtra",
            "signals": ["Brasil", "fintech", "site oficial", "evidência pública"],
        }

        evidence = build_startup_source_evidence(candidate)

        self.assertEqual([item["kind"] for item in evidence], ["official_site", "news"])
        self.assertGreaterEqual(startup_source_confidence(candidate), 80)

    def test_collect_discoveries_interleaves_source_adapters(self) -> None:
        class FakeAdapter:
            def __init__(self, source_url: str, source_label: str | None = None) -> None:
                self.source_url = source_url

            def collect(self, max_items: int = 20) -> list[dict[str, object]]:
                prefix = self.source_url.removeprefix("https://")
                return [
                    {
                        "startup_name": f"{prefix} Startup {index}",
                        "source": f"{prefix}_news",
                    }
                    for index in range(1, 4)
                ]

        original_adapters = startup_discovery_module.DISCOVERY_ADAPTERS
        try:
            startup_discovery_module.DISCOVERY_ADAPTERS = (
                ("fonte-a.test", FakeAdapter),
                ("fonte-b.test", FakeAdapter),
            )
            collection = collect_discoveries_from_sources(
                ["https://fonte-a.test", "https://fonte-b.test"],
                max_items=4,
            )
        finally:
            startup_discovery_module.DISCOVERY_ADAPTERS = original_adapters

        self.assertEqual(
            [item["startup_name"] for item in collection["results"]],
            [
                "fonte-a.test Startup 1",
                "fonte-b.test Startup 1",
                "fonte-a.test Startup 2",
                "fonte-b.test Startup 2",
            ],
        )

    def test_startup_source_check_summarizes_quality_metrics(self) -> None:
        summary = summarize_source_result(
            source_url="https://exame.com/negocios/",
            adapter_name="ExameDiscoveryAdapter",
            discoveries=[
                {
                    "startup_name": "Vixtra",
                    "sector": "fintech",
                    "confidence": 68,
                    "article_title": "Vixtra capta rodada para expandir fintech",
                    "article_url": "https://exame.com/vixtra",
                },
                {
                    "startup_name": "Vixtra Ltda.",
                    "sector": "fintech",
                    "confidence": 70,
                    "article_title": "Vixtra anuncia crescimento",
                    "article_url": "https://exame.com/vixtra-2",
                },
                {
                    "startup_name": "RouteOps",
                    "sector": "unknown",
                    "confidence": 54,
                    "article_title": "RouteOps recebe investimento",
                    "article_url": "https://exame.com/routeops",
                },
            ],
        )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["quality_status"], "warn")
        self.assertTrue(
            any("duplicacao" in reason for reason in summary["quality_reasons"])
        )
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["valid_names"], 3)
        self.assertEqual(summary["valid_name_ratio"], 1.0)
        self.assertEqual(summary["duplicate_names"], 1)
        self.assertEqual(summary["duplicate_ratio"], 0.333)
        self.assertEqual(summary["unknown_sector"], 1)
        self.assertEqual(summary["unknown_sector_ratio"], 0.333)
        self.assertEqual(summary["average_confidence"], 64.0)
        self.assertEqual(summary["sectors"]["fintech"], 2)
        self.assertEqual(summary["examples"][0]["startup_name"], "Vixtra")

    def test_startup_source_quality_evaluation_classifies_fail_warn_and_pass(self) -> None:
        passing_status, passing_reasons = evaluate_source_quality(
            error=None,
            total=4,
            valid_names=4,
            duplicate_names=0,
            unknown_sector=1,
            average_confidence=68.0,
        )
        warning_status, warning_reasons = evaluate_source_quality(
            error=None,
            total=4,
            valid_names=4,
            duplicate_names=2,
            unknown_sector=3,
            average_confidence=50.0,
        )
        failing_status, failing_reasons = evaluate_source_quality(
            error=None,
            total=0,
            valid_names=0,
            duplicate_names=0,
            unknown_sector=0,
            average_confidence=0.0,
        )

        self.assertEqual(passing_status, "pass")
        self.assertEqual(passing_reasons, [])
        self.assertEqual(warning_status, "warn")
        self.assertGreaterEqual(len(warning_reasons), 2)
        self.assertEqual(failing_status, "fail")
        self.assertTrue(any("nenhuma descoberta" in reason for reason in failing_reasons))

    def test_startup_source_check_uses_cli_sources_when_provided(self) -> None:
        sources = configured_source_urls(
            "https://exame.com/negocios/, https://braziljournal.com/, invalid"
        )

        self.assertEqual(
            sources,
            ["https://exame.com/negocios/", "https://braziljournal.com/"],
        )

    def test_startup_keys_deduplicate_common_name_variations(self) -> None:
        self.assertEqual(startup_name_key(" VIXTRA Ltda. "), "vixtra")
        self.assertEqual(startup_key("Vixtra S.A."), "vixtra")

    def test_use_discovered_startups_imports_new_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            discovery_path = str(Path(directory) / "discoveries.csv")
            source_path = str(Path(directory) / "startups.csv")
            write_discoveries(
                discovery_path,
                [
                    {
                        "startup_name": "Vixtra",
                        "country_code": "BR",
                        "sector": "fintech",
                        "source": "startupi_news",
                        "source_url": "https://startupi.com.br/vixtra",
                        "article_title": "Vixtra levanta rodada Série A",
                        "article_url": "https://startupi.com.br/vixtra",
                        "description": "Vixtra levanta rodada Série A",
                        "signals": ["fintech", "Brasil"],
                        "confidence": 72,
                        "discovered_at": "2026-06-24T00:00:00+00:00",
                        "status": "new",
                    }
                ],
            )

            result = use_discovered_startups(
                discovery_path=discovery_path,
                startup_source_path=source_path,
                min_confidence=50,
            )
            candidates = load_startup_candidates(source_path)

            self.assertEqual(result["imported"], 1)
            self.assertIn("Vixtra", {candidate["startup_name"] for candidate in candidates})


class ScrapingUtilityTests(unittest.TestCase):
    def test_brazilian_startup_signal_accepts_accents(self) -> None:
        text = (
            "Startup de Sao Paulo com inteligencia artificial, dados e "
            "plataforma de software para o Brasil."
        )

        self.assertEqual(
            normalize_text("São Paulo, inteligência e operação"),
            "sao paulo, inteligencia e operacao",
        )
        self.assertTrue(has_brazilian_startup_signal("https://example.com", text))

    def test_extract_candidate_links_keeps_internal_relevant_pages(self) -> None:
        links = [
            "/product",
            "/about#team",
            "https://example.com/docs",
            "https://other.com/product",
            "mailto:hello@example.com",
            "/assets/logo.png",
        ]

        candidates = extract_candidate_links("https://example.com", links, max_links=10)

        self.assertIn("https://example.com/product", candidates)
        self.assertIn("https://example.com/about", candidates)
        self.assertIn("https://example.com/docs", candidates)
        self.assertNotIn("https://other.com/product", candidates)


class ProfileExtractionTests(unittest.TestCase):
    def test_extracts_structured_profile_from_manual_and_public_sources(self) -> None:
        profile = extract_structured_profile(
            description=(
                "Startup usa LLM, RAG e agentes de IA para atendimento corporativo."
            ),
            source_pages=[
                {
                    "source_url": "https://startup.example/sobre",
                    "text": (
                        "A empresa foi fundada por Ana Silva e Bruno Costa. "
                        "Captou rodada seed para expandir operacoes no Brasil. "
                        "Atende clientes enterprise em saude e financeiro. "
                        "A plataforma usa machine learning, NLP e APIs em producao."
                    ),
                }
            ],
        )

        self.assertTrue(profile.founders)
        self.assertTrue(profile.funding)
        self.assertTrue(profile.customers)
        self.assertTrue(profile.technologies)
        self.assertTrue(profile.ai_signals)
        self.assertEqual(str(profile.founders[0].source_url), "https://startup.example/sobre")


class BriefingTests(unittest.TestCase):
    def test_briefing_includes_evidence_and_recommendations(self) -> None:
        source = StartupSourceSummary(
            source_url="https://startup.example",
            status="collected",
            characters=1200,
            excerpt="Produto com LLM em producao.",
        )
        recommendations = [
            StartupRecommendation(
                technology="NVIDIA NIM",
                category="inference",
                priority="high",
                technical_reason=(
                    "Serving otimizado para modelos de IA com deploy de inferencia "
                    "em producao, baixa latencia e operacao monitoravel."
                ),
                business_reason="Reduz risco tecnico em producao.",
                source_url="https://developer.nvidia.com/nim",
                retrieval_score=0.82,
            )
        ]

        checks = validate_evidence(
            description="Startup usa LLM em producao.",
            source_summary=source,
            gaps=["latencia de inferencia"],
            recommendations=recommendations,
        )
        briefing = generate_briefing_markdown(
            startup_name="Demo AI",
            sector="healthcare",
            classification="ai_native",
            ai_native_score=88,
            wrapper_risk_score=22,
            nvidia_fit_score=91,
            source_summary=source,
            gaps=["latencia de inferencia"],
            recommendations=recommendations,
            evidence_checks=checks,
            limitations=["Analise MVP."],
            search_plan=StartupSearchPlan(
                query="Demo AI healthcare latencia de inferencia",
                search_terms=["Demo AI", "healthcare", "latencia de inferencia"],
                source_priorities=["startup_catalog", "official_website"],
                evidence_targets=["produto", "sinais_de_ia"],
            ),
        )

        self.assertGreaterEqual(len(checks), 4)
        self.assertIn("# Briefing executivo - Demo AI", briefing)
        self.assertIn("NVIDIA NIM", briefing)
        self.assertIn("latencia de inferencia", briefing)
        self.assertIn("Complexidade de implementacao", briefing)
        self.assertIn("Proxima acao", briefing)
        self.assertIn("Plano de busca", briefing)
        self.assertIn("Playbook de abordagem NVIDIA", briefing)
        self.assertIn("Timing sugerido", briefing)
        self.assertIn("Pergunta de descoberta", briefing)

    def test_briefing_includes_structured_profile_when_available(self) -> None:
        profile = extract_structured_profile(
            description="Startup usa LLM e IA generativa para automacao.",
            source_pages=[
                {
                    "source_url": "https://startup.example/clientes",
                    "text": "Atende clientes enterprise e usa machine learning em producao.",
                }
            ],
        )

        briefing = generate_briefing_markdown(
            startup_name="Demo AI",
            sector="healthcare",
            classification="ai_native",
            ai_native_score=80,
            wrapper_risk_score=20,
            nvidia_fit_score=85,
            source_summary=None,
            gaps=[],
            recommendations=[],
            evidence_checks=[],
            limitations=[],
            structured_profile=profile,
        )

        self.assertIn("Perfil estruturado extraido", briefing)
        self.assertIn("Clientes e casos", briefing)
        self.assertIn("machine learning", briefing)

    def test_briefing_can_include_pipeline_trace(self) -> None:
        briefing = generate_briefing_markdown(
            startup_name="Demo AI",
            sector="healthcare",
            classification="ai_native",
            ai_native_score=80,
            wrapper_risk_score=20,
            nvidia_fit_score=85,
            source_summary=None,
            gaps=[],
            recommendations=[],
            evidence_checks=[],
            limitations=[],
            pipeline_trace=[
                {
                    "agent": "NVIDIA RAG Agent",
                    "name": "nvidia_rag_retrieval",
                    "status": "completed",
                    "duration_ms": 12,
                    "summary": "Busca executada.",
                }
            ],
        )

        self.assertIn("Pipeline executada", briefing)
        self.assertIn("NVIDIA RAG Agent", briefing)

    def test_briefing_pdf_export_generates_pdf_bytes(self) -> None:
        pdf = build_pdf("# Briefing executivo - Demo\n\n## Resumo\n- Fit alto")

        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Helvetica-Bold", pdf)
        self.assertIn(b"Seraphim Scout", pdf)
        self.assertIn(b"%%EOF", pdf)

    def test_evidence_validator_blocks_weak_recommendation_without_startup_evidence(self) -> None:
        recommendations = [
            StartupRecommendation(
                technology="NVIDIA NIM",
                category="inference",
                priority="medium",
                technical_reason="Trecho curto.",
                business_reason="Pode ajudar.",
                source_url="",
                retrieval_score=0.12,
            )
        ]

        checks = validate_evidence(
            description=None,
            source_summary=None,
            gaps=["latencia"],
            recommendations=recommendations,
        )

        blocked = [check for check in checks if check.blocks_recommendation]
        self.assertTrue(blocked)
        self.assertTrue(any(check.severity == "warning" for check in blocked))
        self.assertTrue(any(check.claim_type == "recommendation" for check in blocked))
        self.assertTrue(any(check.blocking_reason for check in blocked))

    def test_evidence_validator_links_sources_to_supported_recommendation(self) -> None:
        source = StartupSourceSummary(
            source_url="https://startup.example",
            status="collected",
            characters=900,
            excerpt="Startup opera LLM em producao com baixa latencia.",
        )
        recommendations = [
            StartupRecommendation(
                technology="NVIDIA NIM",
                category="inference",
                priority="high",
                technical_reason=(
                    "NVIDIA NIM oferece microservicos otimizados para servir modelos "
                    "de IA generativa em producao com menor latencia operacional."
                ),
                business_reason="Acelera a entrada em producao com menos risco tecnico.",
                source_url="https://developer.nvidia.com/nim",
                retrieval_score=0.81,
            )
        ]

        checks = validate_evidence(
            description="Startup brasileira usa LLM em producao.",
            source_summary=source,
            source_pages=[
                {
                    "source_url": "https://startup.example/produto",
                    "characters": 900,
                    "excerpt": "LLM em producao.",
                }
            ],
            gaps=["latencia de inferencia"],
            recommendations=recommendations,
        )

        recommendation_check = next(
            check for check in checks if check.claim_type == "recommendation"
        )
        self.assertFalse(recommendation_check.blocks_recommendation)
        self.assertEqual(recommendation_check.support, "direct_and_retrieved")
        self.assertIn("https://developer.nvidia.com/nim", recommendation_check.source_urls)
        self.assertTrue(
            any(
                evidence_id.startswith("startup_page:")
                for evidence_id in recommendation_check.evidence_ids
            )
        )
        self.assertTrue(
            any(
                evidence_id.startswith("nvidia_source:nvidia-nim")
                for evidence_id in recommendation_check.evidence_ids
            )
        )

    def test_evidence_validator_blocks_low_retrieval_score_with_reason(self) -> None:
        source = StartupSourceSummary(
            source_url="https://startup.example",
            status="collected",
            characters=900,
            excerpt="Startup opera LLM em producao com baixa latencia.",
        )
        recommendations = [
            StartupRecommendation(
                technology="NVIDIA RAPIDS",
                category="data_processing",
                priority="medium",
                technical_reason=(
                    "RAPIDS acelera processamento tabular em GPU para pipelines de "
                    "dados, mas o trecho recuperado ficou pouco aderente ao gap."
                ),
                business_reason="Pode acelerar experimentos de dados.",
                source_url="https://rapids.ai/",
                retrieval_score=0.18,
            )
        ]

        checks = validate_evidence(
            description="Startup brasileira usa LLM em producao.",
            source_summary=source,
            source_pages=[
                {
                    "source_url": "https://startup.example/produto",
                    "characters": 900,
                }
            ],
            gaps=["latencia de inferencia"],
            recommendations=recommendations,
        )

        recommendation_check = next(
            check for check in checks if check.claim_type == "recommendation"
        )
        self.assertTrue(recommendation_check.blocks_recommendation)
        self.assertEqual(recommendation_check.recommendation_technology, "NVIDIA RAPIDS")
        self.assertIn("score de recuperacao", recommendation_check.blocking_reason or "")

    def test_evidence_validator_accepts_configurable_hash_retrieval_floor(self) -> None:
        recommendations = [
            StartupRecommendation(
                technology="NeMo Guardrails",
                category="governance",
                priority="high",
                technical_reason=(
                    "NeMo Guardrails ajuda a aplicar politicas de seguranca, "
                    "governanca e controle de respostas para aplicacoes com LLM."
                ),
                business_reason="Reduz risco operacional em aplicacoes generativas.",
                source_url="https://github.com/NVIDIA/NeMo-Guardrails",
                retrieval_score=0.18,
            )
        ]

        checks = validate_evidence(
            description="Startup usa IA generativa e LLM em producao.",
            source_summary=None,
            gaps=["governanca de IA"],
            recommendations=recommendations,
            min_recommendation_retrieval_score=0.15,
        )

        recommendation_check = next(
            check for check in checks if check.claim_type == "recommendation"
        )
        self.assertFalse(recommendation_check.blocks_recommendation)
        self.assertEqual(recommendation_check.support, "manual_and_retrieved")
        self.assertIn("retrieval_score>=0.15", recommendation_check.minimum_required or "")


if __name__ == "__main__":
    unittest.main()
